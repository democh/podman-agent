"""通用意图识别器：注册表驱动，支持声明式扩展。

架构：
    IntentDef  —— 意图定义（名称、关键词、guide文件、描述、提示）
    INTENT_REGISTRY —— 所有已注册意图
    IntentDetector  —— 两层检测（关键词预筛 + LLM 批量确认）

扩展新意图只需在 INTENT_REGISTRY 中追加一条 IntentDef，无需改动检测逻辑。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

if TYPE_CHECKING:
    from ..core.llm import LLMClient

_MD_DIR = Path(__file__).parent / "md"

# LLM 意图确认的超时时间（秒）—— 快速失败，不阻塞主流程
_LLM_CONFIRM_TIMEOUT = 4.0
# 关键词命中数 >= 此值时视为高置信度，跳过 LLM 确认
_HIGH_CONFIDENCE_THRESHOLD = 2


# ─── 意图定义 ─────────────────────────────────────────

@dataclass
class IntentDef:
    """单条意图定义。"""

    name: str
    """意图标识符，如 chart / search / document"""

    keywords: tuple[str, ...]
    """第一层快速预筛关键词（宽松匹配，避免漏检）"""

    description: str
    """给 LLM 分类器的意图说明（一句话描述什么情况命中此意图）"""

    guide_file: str | None = None
    """命中后加载的 guide md 文件名（位于 prompts/md/ 下），None 表示无独立指南"""

    hint: str = ""
    """guide_file 为 None 时，命中后注入的简短提示文本"""

    enabled: bool = True
    """是否启用此意图检测"""


# ─── 意图注册表 ───────────────────────────────────────

INTENT_REGISTRY: list[IntentDef] = [
    IntentDef(
        name="chart",
        keywords=(
            "图表", "柱状", "折线", "饼图", "散点", "雷达", "漏斗",
            "仪表盘", "热力图", "K线", "箱线", "桑基", "树图", "关系图",
            "旭日图", "矩形树", "象形柱", "面积图", "可视化",
            "chart", "echarts", "数据图", "统计图", "趋势图", "分布图",
            "占比", "对比图", "组织结构", "画个", "帮我画", "生成图",
            "绘制", "做个图",
        ),
        guide_file="charts.md",
        description="用户需要生成数据图表或进行数据可视化（柱状图、折线图、饼图、散点图等）",
    ),
    IntentDef(
        name="search",
        keywords=(
            "搜索", "查一下", "查询", "搜一下", "帮我查", "最新",
            "新闻", "百度", "google", "bing", "网上", "互联网",
            "热点", "实时", "今天", "最近发生", "了解一下",
            "search", "look up", "find out",
        ),
        guide_file=None,
        description="用户需要从互联网搜索获取最新信息或验证事实",
        hint="用户意图涉及信息搜索，优先使用 web_search 工具获取最新信息，必要时用 fetch_page 提取详情。",
    ),
    IntentDef(
        name="document",
        keywords=(
            "文档", "文件", "解析", "上传", "pdf", "word", "excel",
            "pptx", "docx", "xlsx", "csv", "导入", "读取文件",
            "分析这个文件", "总结文档", "翻译文档", "提取内容",
            "document", "upload", "parse",
        ),
        guide_file=None,
        description="用户需要解析、处理或分析上传的文档文件",
        hint="用户意图涉及文档处理，关注消息中的上传文件内容。如需进一步处理，可用 read_file 读取 download/ 目录下的原文件。",
    ),
]


# ─── 意图检测器 ───────────────────────────────────────

class IntentDetector:
    """通用意图识别器：关键词预筛 + LLM 批量确认。"""

    def __init__(self, llm: "LLMClient") -> None:
        self._llm = llm

    def detect(self, user_input: str) -> list[str]:
        """检测用户输入命中的意图列表。

        优化策略：
        - 高置信度（多关键词命中）直接确认，跳过 LLM
        - 低置信度才调用 LLM，并设置严格超时

        Returns:
            命中的意图 name 列表，如 ["chart", "search"]
        """
        # 第一层：关键词快速预筛
        candidates, high_conf = self._keyword_prefilter(user_input)
        if not candidates:
            return []

        # 高置信度意图直接确认，无需 LLM
        confirmed = [c.name for c in high_conf]

        # 低置信度意图才需要 LLM 确认
        low_conf = [c for c in candidates if c not in high_conf]
        if low_conf:
            llm_confirmed = self._llm_confirm(user_input, low_conf)
            confirmed.extend(llm_confirmed)

        return confirmed

    def get_guide(self, intent_name: str) -> str | None:
        """根据意图名称加载对应的 guide 内容。

        Returns:
            guide 文本（md 内容或 hint 提示），无内容时返回 None
        """
        intent_def = self._find_def(intent_name)
        if intent_def is None:
            return None

        # 优先加载 guide_file
        if intent_def.guide_file:
            guide_path = _MD_DIR / intent_def.guide_file
            if guide_path.exists():
                return guide_path.read_text(encoding="utf-8").strip()

        # 否则返回 hint
        if intent_def.hint:
            return intent_def.hint

        return None

    # ── 内部方法 ──────────────────────────────────────

    def _keyword_prefilter(self, text: str) -> tuple[list[IntentDef], list[IntentDef]]:
        """第一层：关键词快速预筛。

        Returns:
            (candidates, high_confidence) - 所有命中的意图 + 高置信度意图
        """
        text_lower = text.lower()
        candidates = []
        high_conf = []
        for intent in INTENT_REGISTRY:
            if not intent.enabled:
                continue
            hit_count = sum(1 for kw in intent.keywords if kw in text_lower)
            if hit_count > 0:
                candidates.append(intent)
                if hit_count >= _HIGH_CONFIDENCE_THRESHOLD:
                    high_conf.append(intent)
        return candidates, high_conf

    def _llm_confirm(self, user_input: str, candidates: list[IntentDef]) -> list[str]:
        """第二层：调用 LLM 批量确认哪些候选意图真正命中。

        一次 LLM 调用判断所有候选意图，减少延迟。
        设置严格超时，失败/超时时回退为全部命中。
        """
        try:
            system_prompt = self._build_classify_prompt(candidates)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input[:300]},
            ]
            # 用线程池 + 超时控制，避免阻塞主流程
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._llm.chat, messages, None, stream=False)
                resp = future.result(timeout=_LLM_CONFIRM_TIMEOUT)
            content = resp["choices"][0]["message"].get("content", "") or ""
            result = json.loads(content.strip())
            confirmed_names = result.get("intents", [])
            # 只返回确实在候选中的意图名
            candidate_names = {c.name for c in candidates}
            return [n for n in confirmed_names if n in candidate_names]
        except (FutureTimeout, Exception):
            # 超时或失败时回退：全部视为命中
            return [c.name for c in candidates]

    def _build_classify_prompt(self, candidates: list[IntentDef]) -> str:
        """动态构建多意图分类 prompt。"""
        intent_list = "\n".join(
            f"- **{c.name}**：{c.description}"
            for c in candidates
        )
        template = _MD_DIR / "intent.md"
        base_prompt = template.read_text(encoding="utf-8").strip()
        return base_prompt.format(intent_list=intent_list)

    def _find_def(self, name: str) -> IntentDef | None:
        """按名称查找意图定义。"""
        for intent in INTENT_REGISTRY:
            if intent.name == name:
                return intent
        return None
