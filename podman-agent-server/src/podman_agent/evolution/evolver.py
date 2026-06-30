"""对话后自动反思：从交互中提取可复用经验并写入记忆系统。

核心逻辑：
- 对话结束后，收集本轮工具调用摘要与对话上下文
- 通过 LLM 进行轻量反思，提取：经验教训、工具洞察、用户偏好
- 去重检查后写入记忆系统（category=knowledge）
- 异步执行，不阻塞用户响应
"""
from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any

from ..prompts import _load_md

if TYPE_CHECKING:
    from ..core.llm import LLMClient
    from ..memory.store import MemoryStore
    from .metrics import MetricsCollector
    from .user_profile import UserProfiler

logger = logging.getLogger(__name__)


class Evolver:
    """自进化核心调度器：管理对话后反思、经验提取与写入。"""

    def __init__(
        self,
        llm: "LLMClient",
        memory: "MemoryStore",
        metrics: "MetricsCollector",
        profiler: "UserProfiler",
        *,
        min_tool_calls: int = 2,
        enabled: bool = True,
    ) -> None:
        self._llm = llm
        self._memory = memory
        self._metrics = metrics
        self._profiler = profiler
        self._min_tool_calls = min_tool_calls
        self._enabled = enabled

    # ── 公开接口 ──────────────────────────────────────────

    def post_conversation_reflect(
        self,
        user_input: str,
        tool_calls: list[dict],
        reply: str,
        *,
        plan_steps: list[str] | None = None,
    ) -> None:
        """对话结束后触发异步反思（不阻塞主线程）。"""
        if not self._enabled:
            return
        # 过滤条件：工具调用数不足时跳过
        if len(tool_calls) < self._min_tool_calls:
            return

        # 异步执行反思
        thread = threading.Thread(
            target=self._reflect_sync,
            args=(user_input, tool_calls, reply, plan_steps),
            daemon=True,
        )
        thread.start()

    # ── 内部实现 ──────────────────────────────────────────

    def _reflect_sync(
        self,
        user_input: str,
        tool_calls: list[dict],
        reply: str,
        plan_steps: list[str] | None,
    ) -> None:
        """同步执行反思逻辑（在后台线程中运行）。"""
        try:
            # 构建对话摘要
            conversation_summary = self._build_conversation_summary(
                user_input, tool_calls, reply, plan_steps
            )

            # 构建工具结果摘要
            tool_results = self._build_tool_results_summary(tool_calls)

            # 获取已有记忆列表（避免重复）
            existing_memories = self._memory.list_all(exclude_conversations=True)

            # 加载反思 prompt 模板
            try:
                template = _load_md("evolution.md")
            except FileNotFoundError:
                template = self._default_evolution_prompt()

            prompt = template.format(
                conversation_summary=conversation_summary,
                tool_results=tool_results,
                existing_memories=existing_memories[:1500],
            )

            # LLM 调用（使用实例默认温度）
            resp = self._llm.chat(
                [{"role": "system", "content": prompt}],
                tools=None,
                stream=False,
            )
            content = resp["choices"][0]["message"].get("content", "")

            # 解析 JSON 结果
            insights = self._parse_reflection_output(content)
            if not insights:
                return

            # 写入记忆系统
            self._apply_insights(insights)

        except Exception as e:
            logger.warning(f"自进化反思失败: {e}")

    def _build_conversation_summary(
        self,
        user_input: str,
        tool_calls: list[dict],
        reply: str,
        plan_steps: list[str] | None,
    ) -> str:
        """构建对话摘要。"""
        parts = [f"用户输入: {user_input[:200]}"]
        if plan_steps:
            parts.append(f"执行计划: {len(plan_steps)} 步")
            for i, step in enumerate(plan_steps[:5], 1):
                parts.append(f"  STEP {i}: {step}")
        parts.append(f"工具调用次数: {len(tool_calls)}")

        # 失败统计
        failures = [tc for tc in tool_calls if tc.get("result", "").startswith("Error:")]
        if failures:
            parts.append(f"失败次数: {len(failures)}")
            for tc in failures[:3]:
                parts.append(f"  - {tc['name']}: {tc.get('result', '')[:100]}")

        parts.append(f"最终回复摘要: {reply[:200]}")
        return "\n".join(parts)

    def _build_tool_results_summary(self, tool_calls: list[dict]) -> str:
        """构建工具结果摘要（去敏）。"""
        lines = []
        for tc in tool_calls[:10]:  # 最多展示 10 个
            name = tc.get("name", "unknown")
            args = tc.get("args", {})
            result = tc.get("result", "")
            success = not result.startswith("Error:")
            status = "OK" if success else "FAIL"

            # 参数摘要（去敏）
            args_brief = ", ".join(
                f"{k}={'...' if len(str(v)) > 30 else v}"
                for k, v in (args.items() if isinstance(args, dict) else [])
            )[:100]

            result_brief = result[:80] if success else result[:120]
            lines.append(f"[{status}] {name}({args_brief}) -> {result_brief}")

        return "\n".join(lines)

    def _parse_reflection_output(self, content: str) -> dict[str, Any] | None:
        """从 LLM 输出中解析结构化反思结果。"""
        # 尝试提取 JSON 块
        content = content.strip()

        # 尝试从 markdown 代码块中提取
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            content = content[start:end].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 尝试宽松解析：找到第一个 { 和最后一个 }
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                try:
                    data = json.loads(content[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    return None
            else:
                return None

        # 验证必须有实质内容
        if not isinstance(data, dict):
            return None
        has_content = (
            data.get("lessons")
            or data.get("should_update")
            or data.get("tool_insights")
            or data.get("user_preference")
        )
        return data if has_content else None

    def _apply_insights(self, insights: dict[str, Any]) -> None:
        """将反思结果写入记忆系统。"""
        # 1. 新经验
        lessons = insights.get("lessons") or []
        for lesson in lessons[:3]:  # 每轮最多写入 3 条
            if not isinstance(lesson, dict):
                continue
            title = lesson.get("title", "").strip()
            content = lesson.get("content", "").strip()
            category = lesson.get("category", "knowledge")
            if not title or not content:
                continue
            # 去重：搜索是否已有类似记忆
            search_result = self._memory.search(title)
            if "未找到" in search_result or "为空" in search_result:
                keywords = lesson.get("keywords", title[:20])
                self._memory.add(title, content, category, keywords)
                logger.info(f"[进化] 新增记忆: {title}")
            else:
                logger.debug(f"[进化] 跳过重复记忆: {title}")

        # 2. 更新已有记忆
        updates = insights.get("should_update") or []
        for upd in updates[:2]:
            if not isinstance(upd, dict):
                continue
            title = upd.get("title", "").strip()
            update_content = upd.get("update", "").strip()
            if not title or not update_content:
                continue
            # 读取已有内容，追加更新
            existing = self._memory.get(title)
            if "Error:" not in existing:
                new_content = existing.split("---", 2)[-1].strip()
                new_content += f"\n\n---\n_进化补充 ({self._now()})_:\n{update_content}"
                self._memory.update(title, new_content)
                logger.info(f"[进化] 更新记忆: {title}")

        # 3. 工具洞察 -> 存入工具优化记忆
        tool_insights = insights.get("tool_insights") or []
        if tool_insights:
            self._save_tool_insights(tool_insights)

        # 4. 用户偏好
        user_pref = insights.get("user_preference")
        if user_pref and isinstance(user_pref, dict):
            confidence = user_pref.get("confidence", 0.5)
            if confidence >= 0.7:
                self._profiler.update_from_insight(user_pref)

    def _save_tool_insights(self, insights: list[dict]) -> None:
        """保存工具使用洞察到专门记忆。"""
        title = "工具使用模式与最佳实践"
        existing = self._memory.get(title)

        new_lines = []
        for insight in insights[:5]:
            if not isinstance(insight, dict):
                continue
            tool = insight.get("tool", "")
            pattern = insight.get("pattern", "")
            note = insight.get("note", "")
            if tool and (pattern or note):
                new_lines.append(f"- **{tool}**: {pattern} ({note})")

        if not new_lines:
            return

        if "Error:" in existing:
            # 首次创建
            content = "# 工具使用模式与最佳实践\n\n" + "\n".join(new_lines)
            self._memory.add(title, content, "knowledge", "工具,最佳实践,模式")
        else:
            # 追加
            body = existing.split("---", 2)[-1].strip()
            body += "\n" + "\n".join(new_lines)
            # 防止过长
            lines = body.splitlines()
            if len(lines) > 50:
                body = "\n".join(lines[-40:])
            self._memory.update(title, body)

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _default_evolution_prompt() -> str:
        """当 evolution.md 不存在时使用的默认模板。"""
        return """# 对话反思

你刚刚完成了一轮对话。请分析这轮交互并提取可复用的经验。

## 本轮对话摘要
{conversation_summary}

## 工具调用结果
{tool_results}

## 已有记忆库
{existing_memories}

## 输出要求

以 JSON 格式输出。仅在有值得记录的新发现时输出对应字段，没有则输出空 JSON `{}`。

```json
{
  "lessons": [{"title": "简明标题", "content": "具体经验内容", "category": "knowledge", "keywords": "关键词1,关键词2"}],
  "should_update": [{"title": "已有记忆标题", "update": "需要补充的内容"}],
  "tool_insights": [{"tool": "工具名", "pattern": "使用模式", "note": "注意事项"}],
  "user_preference": {"key": "偏好维度", "value": "偏好值", "confidence": 0.8}
}
```

重要约束：
- 只记录真正有复用价值的经验，不记录琐碎信息
- 经验内容必须具体、可操作，包含解决方案
- 避免与已有记忆重复
- confidence 取值 0-1，仅 >= 0.7 的偏好会被采纳
"""
