"""Plan-Execute-Reflect：任务规划、步骤上下文注入、执行后反思。

职责：
- 分析用户输入，判断是否需要生成执行计划
- 在每步 LLM 调用前注入当前步骤上下文
- 工具执行后进行反思评估（DONE / RETRY / REPLAN）
- 维护计划状态（步骤列表、当前索引、重试计数等）
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..prompts import (
    build_planning_prompt,
    build_reflection_prompt,
    build_tools_overview,
)

if TYPE_CHECKING:
    from .agent import Agent


# ── 工具函数 ────────────────────────────────────────────────────

def format_plan_progress(steps: list[str], current_idx: int) -> str:
    """格式化计划进度展示（✅ 已完成 / 🔄 进行中 / ⬜ 待执行）。"""
    lines = ["# 执行计划\n"]
    for i, step in enumerate(steps):
        if i < current_idx:
            status = "✅"
        elif i == current_idx:
            status = "🔄"
        else:
            status = "⬜"
        lines.append(f"{status} STEP {i + 1}: {step}")
    return "\n".join(lines)


def parse_plan_steps(text: str) -> list[str]:
    """从 LLM 输出中解析步骤列表（匹配 STEP N: ...）。"""
    pattern = r"STEP\s+\d+\s*[:：]\s*(.+)"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return [m.strip() for m in matches if m.strip()]


def parse_reflection_result(text: str) -> str:
    """从反思输出中解析结果标记（DONE / RETRY / REPLAN）。"""
    text_upper = text.upper()
    if "RESULT: DONE" in text_upper:
        return "DONE"
    if "RESULT: RETRY" in text_upper:
        return "RETRY"
    if "RESULT: REPLAN" in text_upper:
        return "REPLAN"
    # 无法解析时默认重试，避免误判完成
    return "RETRY"


# ── 智能规划触发 ─────────────────────────────────────────────────

# 简单问候/闲聊模式：无需规划，直接跳过 LLM 调用
_GREETING_PATTERNS = {
    "你好", "hi", "hello", "hey", "嗨", "早上好", "晚上好",
    "谢谢", "thanks", "thank you", "再见", "bye", "ok", "好的",
}


def _should_skip_plan(user_input: str) -> bool:
    """快速判断是否跳过规划（仅极短输入/问候语）。

    其余所有输入均交由 LLM 自主判断是否需要拆解。
    """
    text = user_input.strip().lower()
    # 极短输入或问候语 → 跳过
    return len(text) < 6 or text in _GREETING_PATTERNS


# ── Planner 类 ──────────────────────────────────────────────────


class Planner:
    """管理 Plan-Execute-Reflect 全流程，持有 Agent 引用以访问共享状态。"""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    # ── 规划 ────────────────────────────────────────────────

    def create_plan(self, user_input: str) -> None:
        """LLM 原生判断是否需要拆解计划，避免关键词启发式的误判。

        策略：
        - 极短输入/问候语 → 直接跳过（无 LLM 调用）
        - 其余所有输入 → 调用 LLM 规划，由 LLM 自主判断是否需要拆解
        - LLM 返回 < 2 步 → 丢弃（简单任务无需计划）
        """
        a = self._agent
        if not a.config.enable_planning:
            return
        # 极短输入/问候语直接跳过，避免无谓的 LLM 调用
        if _should_skip_plan(user_input):
            return
        if a._stop_requested:
            return
        try:
            plan_prompt = build_planning_prompt(
                tools_overview=build_tools_overview(),
            )
            plan_messages = [
                {"role": "system", "content": plan_prompt},
                {"role": "user", "content": user_input},
            ]
            resp = a.llm.chat(plan_messages, tools=[], stream=False)
            a._track_usage(resp)
            plan_text = resp["choices"][0]["message"].get("content", "")

            steps = parse_plan_steps(plan_text)
            if len(steps) < 2:
                return

            a._plan_steps = steps
            a._current_step_idx = 0
            self.reset_flags()

            plan_display = format_plan_progress(steps, 0)
            a.messages.append({"role": "system", "content": plan_display})
            a._emit({"type": "plan_created", "steps": steps})
        except Exception as e:
            a._emit({"type": "warning", "content": f"规划失败，降级为直接执行：{e}"})

    # ── 步骤上下文注入 ──────────────────────────────────────

    def inject_step_context(self) -> None:
        """在每次 LLM 调用前注入当前步骤上下文（仅步骤切换时注入一次）。"""
        a = self._agent
        if not a._plan_steps or a._current_step_idx < 0:
            return
        # 避免重复注入同一步骤的上下文
        if a._last_injected_step == a._current_step_idx:
            return
        a._last_injected_step = a._current_step_idx

        if a._current_step_idx >= len(a._plan_steps):
            a.messages.append({
                "role": "system",
                "content": "所有计划步骤已完成，请给出最终总结。",
            })
            return

        step = a._plan_steps[a._current_step_idx]
        idx = a._current_step_idx + 1
        total = len(a._plan_steps)
        context = (
            f"## 当前执行进度\n\n"
            f"计划共 {total} 步，当前第 {idx} 步：\n"
            f"**STEP {idx}: {step}**\n\n"
            f"请聚焦于完成当前步骤。"
        )
        a.messages.append({"role": "system", "content": context})

    # ── 反思 ────────────────────────────────────────────────

    def reflect(self) -> None:
        """工具执行后进行反思，决定是否需要重试或调整计划。"""
        a = self._agent
        if a._current_step_idx < 0 or a._current_step_idx >= len(a._plan_steps):
            return
        if a._stop_requested:
            return

        # 收集最近的工具结果（跳过 system 消息，到 assistant 为止）
        recent_results = []
        for m in reversed(a.messages):
            role = m.get("role", "")
            if role == "tool":
                recent_results.insert(0, m.get("content", ""))
            elif role == "assistant":
                break
        result_text = "\n".join(recent_results) if recent_results else "（无工具结果）"

        # 构建反思提示
        completed = "\n".join(
            f"STEP {i+1}: {s}" for i, s in enumerate(a._plan_steps[:a._current_step_idx])
        )
        current_step = f"STEP {a._current_step_idx + 1}: {a._plan_steps[a._current_step_idx]}"
        plan_text = format_plan_progress(a._plan_steps, a._current_step_idx)

        reflection_prompt = build_reflection_prompt(
            plan=plan_text,
            completed=completed,
            current_step=current_step,
            result=result_text,
        )

        try:
            resp = a.llm.chat(
                [{"role": "system", "content": reflection_prompt}],
                tools=[],
                stream=False,
            )
            a._track_usage(resp)
            reflection_text = resp["choices"][0]["message"].get("content", "")
        except Exception as e:
            a._emit({"type": "warning", "content": f"反思调用失败，默认继续：{e}"})
            return

        result = parse_reflection_result(reflection_text)
        a._emit({"type": "reflection", "result": result, "detail": reflection_text[:200]})

        if result == "DONE":
            a._current_step_idx += 1
            self.reset_flags()

        elif result == "RETRY":
            a._step_retries += 1
            if a._step_retries >= a.config.max_retries_per_step:
                a._emit({"type": "warning", "content": "步骤重试已达上限，跳过当前步骤"})
                a._current_step_idx += 1
                self.reset_flags()
            elif a._lats_fallback:
                fallback = a._lats_fallback.pop(0)
                a._last_injected_step = -2  # 新策略，重新注入
                a.messages.append({
                    "role": "system",
                    "content": (
                        f"上一步执行未成功。请改用以下备选策略重试：\n\n"
                        f"**{fallback}**\n\n"
                        f"反思：{reflection_text[:300]}"
                    ),
                })
            else:
                a.messages.append({
                    "role": "system",
                    "content": f"上一步执行未成功，请分析原因并调整策略重试。\n反思：{reflection_text[:500]}",
                })

        elif result == "REPLAN":
            new_steps = parse_plan_steps(reflection_text)
            if new_steps:
                # 保留已完成步骤，用新步骤替换当前及剩余步骤
                a._plan_steps = a._plan_steps[:a._current_step_idx] + new_steps
                # 不前进索引，从新计划首步重新执行
                a._step_retries = 0
                self.reset_flags()
                # 关键修复：清理 LATS 残留状态，避免旧方案干扰新计划
                a.lats.clear_fallbacks()
                a._lats_done_step = -1
                plan_display = format_plan_progress(a._plan_steps, a._current_step_idx)
                a.messages.append({
                    "role": "system",
                    "content": f"计划已调整：\n{plan_display}\n继续执行。",
                })
            else:
                a._current_step_idx += 1
                self.reset_flags()

    # ── 状态重置 ────────────────────────────────────────────

    def reset_flags(self) -> None:
        """重置步骤切换时的标志位（_step_retries / _lats_done_step / _last_injected_step）。"""
        a = self._agent
        a._step_retries = 0
        a._lats_done_step = -1
        a._last_injected_step = -2
