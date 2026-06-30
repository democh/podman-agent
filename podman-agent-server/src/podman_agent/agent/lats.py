"""LATS 候选搜索 + 上下文管理。

LatsStrategy：
- 每步生成 K 个候选方案，评估择优后注入指导消息
- 备选方案存入 fallback 队列供 RETRY 使用

ContextManager：
- token 累计与压缩：超阈值时裁剪历史、重注入计划进度
- LLM 摘要压缩：压缩前对旧消息生成摘要，保留关键上下文
- Token 预警：达到 70% 阈值时发射警告事件
- 手动压缩：支持前端主动触发压缩
- 循环检测：滑动窗口检测重复工具调用模式
- guardrails 定期注入、skills 注入
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..prompts import (
    build_evaluation_prompt,
    build_multi_turn_guardrails,
)
from .planner import format_plan_progress

if TYPE_CHECKING:
    from .agent import Agent


def _estimate_tokens(text: str) -> int:
    """基于字符数的粗略 token 估算（≈ 4 字符 / token），作为 API usage 缺失时的 fallback。"""
    return max(1, len(text) // 4)


# ── LatsStrategy ────────────────────────────────────────────────


# 步骤风险分类关键词：用于 LATS 选择性触发
_HIGH_RISK_KEYWORDS = [
    "删除", "覆盖", "修改", "写入", "部署", "发布", "迁移",
    "重构", "架构", "数据库", "安装", "配置",
    "delete", "overwrite", "deploy", "migrate", "refactor",
    "database", "install", "config", "write", "shell",
    "执行", "运行", "execute", "run", "build",
]
_LOW_RISK_KEYWORDS = [
    "读取", "查看", "搜索", "列出", "检查", "分析",
    "read", "list", "search", "find", "check", "analyze", "show",
]


def _step_needs_branch(step_text: str) -> bool:
    """评估步骤是否具有充分复杂度/风险，值得 LATS 多候选搜索。

    只对高风险步骤触发 branch，低风险的单纯信息获取步骤直接跳过，
    节省 2 次 LLM 调用（候选生成 + 评估择优）。
    """
    text = step_text.lower()
    # 明确低风险：跳过
    if any(kw in text for kw in _LOW_RISK_KEYWORDS):
        if not any(kw in text for kw in _HIGH_RISK_KEYWORDS):
            return False
    # 高风险关键词命中：触发
    if any(kw in text for kw in _HIGH_RISK_KEYWORDS):
        return True
    # 默认：对较长步骤描述触发（可能较复杂）
    return len(text) > 30


class LatsStrategy:
    """LATS 候选方案搜索，持有 Agent 引用以访问共享状态。"""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def clear_fallbacks(self) -> None:
        """清空备选方案队列（REPLAN 时调用，避免旧方案污染新计划）。"""
        self._agent._lats_fallback = []

    def should_branch(self, step_text: str) -> bool:
        """选择性触发：只对高风险/复杂步骤进行 branch。"""
        return _step_needs_branch(step_text)

    def branch(self) -> None:
        """生成多个候选方案，评估择优后注入指导消息。"""
        a = self._agent
        if a._current_step_idx < 0 or a._current_step_idx >= len(a._plan_steps):
            return
        if a._stop_requested:
            return
        # 选择性触发：低风险步骤跳过 LATS
        current_step = a._plan_steps[a._current_step_idx]
        if not self.should_branch(current_step):
            a._emit({"type": "lats_skip", "step": a._current_step_idx + 1, "reason": "低风险步骤"})
            return

        current_goal = a._plan_steps[a._current_step_idx]
        k = a.config.lats_candidates

        # 收集最近的对话上下文（供候选生成参考）
        context_parts = []
        for m in a.messages[-8:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if content and role in ("user", "assistant", "tool"):
                context_parts.append(f"[{role}] {content[:300]}")
        context = "\n".join(context_parts) if context_parts else "（无上下文）"

        try:
            # 1. 生成 K 个候选方案
            gen_prompt = (
                f"针对当前目标，提出 {k} 种不同的执行策略。\n\n"
                f"## 当前目标\n{current_goal}\n\n"
                f"## 对话上下文\n{context}\n\n"
                f"## 要求\n"
                f"- 每种策略用一两句话描述具体做法\n"
                f"- 策略之间应有实质性差异，不要重复\n"
                f"- 按 CANDIDATE N: 格式输出\n"
            )
            gen_resp = a.llm.chat(
                [{"role": "system", "content": gen_prompt}],
                tools=[],
                stream=False,
            )
            a._track_usage(gen_resp)
            candidates_text = gen_resp["choices"][0]["message"].get("content", "")
            candidates = _parse_candidates(candidates_text)

            if len(candidates) < 2:
                return

            # 2. 评估并择优
            candidates_display = "\n".join(
                f"CANDIDATE {i+1}: {c}" for i, c in enumerate(candidates)
            )
            eval_prompt = build_evaluation_prompt(
                goal=current_goal,
                context=context,
                candidates=candidates_display,
            )
            eval_resp = a.llm.chat(
                [{"role": "system", "content": eval_prompt}],
                tools=[],
                stream=False,
            )
            a._track_usage(eval_resp)
            eval_text = eval_resp["choices"][0]["message"].get("content", "")
            pick_idx = _parse_pick(eval_text)
        except Exception as e:
            a._emit({"type": "warning", "content": f"LATS 评估失败，跳过：{e}"})
            return

        # 3. 将最优方案注入对话，其余放入备选队列
        best = candidates[pick_idx]
        a._lats_fallback = [c for i, c in enumerate(candidates) if i != pick_idx]

        a.messages.append({
            "role": "system",
            "content": (
                f"## 推荐执行方案\n\n"
                f"从 {len(candidates)} 个候选方案中评估选出最优策略：\n\n"
                f"**{best}**\n\n"
                f"请基于此策略执行当前步骤。"
            ),
        })

        a._emit({
            "type": "lats_pick",
            "pick": pick_idx + 1,
            "total": len(candidates),
            "chosen": best[:100],
        })


# ── 解析工具函数 ────────────────────────────────────────────────


def _parse_candidates(text: str) -> list[str]:
    """从 LLM 输出中解析候选方案（匹配 CANDIDATE N: ...）。"""
    pattern = r"CANDIDATE\s+\d+\s*[:：]\s*(.+)"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return [m.strip() for m in matches if m.strip()]


def _parse_pick(text: str) -> int:
    """从评估输出中解析选择的候选编号（0-based index）。"""
    pattern = r"PICK\s*[:：]\s*(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        idx = int(match.group(1)) - 1  # 转为 0-based
        return max(0, idx)
    return 0  # 默认选第一个


# ── ContextManager ──────────────────────────────────────────────


class ContextManager:
    """上下文管理：token 追踪、压缩、循环检测、guardrails/skills 注入。"""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    # ── token 追踪 ──────────────────────────────────────────

    def track_usage(self, resp: dict) -> None:
        """从 LLM 响应中提取 token 用量并更新累计值。"""
        usage = resp.get("usage") or {}
        if usage:
            self._agent._total_tokens = usage.get(
                "total_tokens", self._agent._total_tokens
            )

    # ── 循环检测 ────────────────────────────────────────────

    def is_looping(self, current: list[tuple[str, str]]) -> bool:
        """滑动窗口循环检测：当前调用签名在历史窗口中出现超过一半则判定为循环。"""
        history = self._agent._call_history
        if not current or not history:
            return False
        match_count = sum(1 for h in history if h == current)
        return match_count >= len(history) // 2 + 1

    # ── 上下文压缩 ──────────────────────────────────────────

    # Token 预警阈值（达到此比例时通知前端）
    _WARNING_RATIO = 0.70
    # 压缩前是否启用 LLM 摘要（关闭则降级为纯截断）
    _SUMMARY_MAX_CHARS = 6000  # 旧消息超过此长度时调用 LLM 摘要

    def maybe_warn_token_usage(self) -> None:
        """Token 用量达到预警阈值时发射警告事件，提醒用户可手动压缩。"""
        a = self._agent
        threshold = a.config.context_token_threshold
        if threshold <= 0:
            return
        ratio = a._total_tokens / threshold
        if ratio >= self._WARNING_RATIO and not getattr(a, '_token_warned', False):
            a._token_warned = True
            pct = int(ratio * 100)
            a._emit({
                "type": "token_warning",
                "total_tokens": a._total_tokens,
                "threshold": threshold,
                "usage_pct": pct,
                "message": f"上下文已使用约 {pct}%，可点击顶栏压缩按钮主动释放空间",
            })
        elif ratio < self._WARNING_RATIO:
            a._token_warned = False  # 重置，支持多次预警

    def _summarize_old_messages(self, old_messages: list[dict]) -> str:
        """对旧消息调用 LLM 生成摘要，保留关键上下文而非直接丢弃。"""
        a = self._agent
        # 将旧消息拼接为文本（截断避免太长）
        parts = []
        for m in old_messages:
            role = m.get('role', '')
            content = m.get('content') or ''
            if content and role in ('user', 'assistant'):
                parts.append(f'[{role}] {content[:400]}')
        if not parts:
            return ''
        conversation_text = '\n'.join(parts)
        if len(conversation_text) < 200:
            return conversation_text  # 太短，直接保留原文

        try:
            summary_resp = a.llm.chat(
                [{"role": "system", "content": (
                    "请将以下对话历史压缩为简洁摘要，保留关键信息（用户目标、已完成的操作、"
                    "重要结论、文件路径）。输出 3-8 句话的中文摘要，不要遗漏关键上下文。\n\n"
                    f"## 对话历史\n{conversation_text[:4000]}"
                )}],
                tools=[],
                stream=False,
            )
            a._track_usage(summary_resp)
            return (summary_resp['choices'][0]['message'].get('content') or '').strip()
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f'压缩摘要 LLM 调用失败: {e}')
            return ''

    def compress_context(self, force: bool = False) -> dict:
        """主动压缩上下文（可由前端手动触发）。返回压缩结果信息。"""
        a = self._agent
        if len(a.messages) <= a.config.keep_recent + 1 and not force:
            return {'compressed': False, 'reason': '消息数不足，无需压缩'}

        system = a.messages[0]
        old_messages = a.messages[1:-a.config.keep_recent] if len(a.messages) > a.config.keep_recent + 1 else a.messages[1:]
        recent = a.messages[-a.config.keep_recent:] if len(a.messages) > a.config.keep_recent else []

        # 确保 recent 不以孤立 tool 消息开头
        while recent and recent[0].get('role') == 'tool':
            recent.pop(0)

        before_count = len(a.messages)
        before_tokens = a._total_tokens

        # LLM 摘要压缩（可选）
        summary = ''
        if old_messages and len(old_messages) > 2:
            summary = self._summarize_old_messages(old_messages)

        # 重建消息列表
        a.messages = [system]
        if summary:
            a.messages.append({
                'role': 'system',
                'content': f'## 历史对话摘要\n\n{summary}\n\n（以上为早期对话的压缩摘要，后续为最近消息）',
            })
        a.messages.extend(recent)

        # 重估 token
        a._total_tokens = sum(
            _estimate_tokens(m.get('content') or '') for m in a.messages
        )
        # 重新注入计划进度
        if a._plan_steps and a._current_step_idx >= 0:
            plan_display = format_plan_progress(a._plan_steps, a._current_step_idx)
            a.messages.append({'role': 'system', 'content': plan_display})
            a._last_injected_step = -2

        after_count = len(a.messages)
        saved_tokens = before_tokens - a._total_tokens
        a._token_warned = False  # 重置预警

        result = {
            'compressed': True,
            'before_messages': before_count,
            'after_messages': after_count,
            'before_tokens': before_tokens,
            'after_tokens': a._total_tokens,
            'saved_tokens': max(0, saved_tokens),
            'has_summary': bool(summary),
        }
        a._emit({'type': 'context_compressed', **result})
        return result

    def maybe_compress(self) -> None:
        """token 超阈值时自动压缩：先尝试 LLM 摘要，再截断历史。"""
        a = self._agent
        if a._total_tokens < a.config.context_token_threshold:
            return
        if len(a.messages) <= a.config.keep_recent + 1:
            return
        # 复用 compress_context，自动触发
        self.compress_context(force=True)

    # ── guardrails 注入 ─────────────────────────────────────

    def inject_guardrails(self, iteration: int) -> None:
        """每隔 N 轮迭代注入 guardrails 提醒，确保约束持续生效。"""
        a = self._agent
        if iteration > 0 and iteration % a.config.guardrails_interval == 0:
            guardrails = build_multi_turn_guardrails()
            a.messages.append({"role": "system", "content": guardrails})

    # ── skills 注入 ─────────────────────────────────────────

    def inject_skills(self) -> None:
        """注入已启用技能的指令到对话中。

        技能不增加工具，而是通过 system 消息注入行为指令。
        每次调用重新加载技能文件，支持热更新。
        """
        a = self._agent
        a.skills.reload()
        instructions = a.skills.get_active_instructions()
        if instructions:
            a.messages.append({"role": "system", "content": instructions})
