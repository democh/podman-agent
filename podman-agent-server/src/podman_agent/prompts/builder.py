"""提示词构建器：从 md/ 子目录加载模板，组装 system prompt / tools overview / guardrails。

每次调用都从文件重新读取，修改 md 文件后无需重启即可生效。
"""
from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

_MD_DIR = Path(__file__).parent / "md"


def _load_md(filename: str) -> str:
    """读取 prompts/md/ 目录下的 Markdown 文件，返回纯文本。"""
    return (_MD_DIR / filename).read_text(encoding="utf-8").strip()


def build_system_prompt(
    workspace: str,
    tools_overview: str = "",
    evolution_adaptations: str = "",
) -> str:
    """根据当前 workspace 与工具概览构建最终 system prompt。

    Args:
        workspace: 工作目录路径
        tools_overview: 工具使用指南
        evolution_adaptations: 自进化 prompt 补丁（动态追加）
    """
    parts = [
        _load_md("system.md"),
        _load_md("memory.md"),
        _load_md("skills.md"),
    ]
    if tools_overview:
        parts.append(f"\n# 可用工具\n{tools_overview}\n")
    # 运行环境：OS + shell + 工作目录 + 当前时间 + 编码
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    python_version = platform.python_version()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts.append(
        f"# 运行环境\n"
        f"- 操作系统: {system} {release} ({machine})\n"
        f"- Python: {python_version}\n"
        f"- 默认编码: UTF-8\n"
        f"- 工作目录: {workspace}\n"
        f"- 当前时间: {now}\n"
        f"- 文件读写统一使用 UTF-8 编码\n"
    )
    # 自进化补丁（基于历史表现动态生成）
    if evolution_adaptations:
        parts.append(evolution_adaptations)
    return "".join(parts)


def build_tools_overview() -> str:
    """读取 tools.md 作为工具使用指南，每次调用重新加载。"""
    return _load_md("tools.md")


def build_multi_turn_guardrails() -> str:
    """读取 guardrails.md 作为多轮约束，每次调用重新加载。"""
    return _load_md("guardrails.md")


def build_planning_prompt(tools_overview: str = "") -> str:
    """读取 planning.md 模板并填充可用工具列表。"""
    template = _load_md("planning.md")
    return template.format(
        tools=tools_overview or "（未指定）",
    )


def build_reflection_prompt(
    plan: str, completed: str, current_step: str, result: str
) -> str:
    """读取 reflection.md 模板并填充上下文，返回完整的反思提示词。"""
    template = _load_md("reflection.md")
    return template.format(
        plan=plan,
        completed=completed or "（无）",
        current_step=current_step,
        result=result[:2000] if len(result) > 2000 else result,
    )


def build_evaluation_prompt(goal: str, context: str, candidates: str) -> str:
    """读取 evaluation.md 模板并填充上下文，返回候选方案评估提示词。"""
    template = _load_md("evaluation.md")
    return template.format(
        goal=goal,
        context=context[:1500] if len(context) > 1500 else context,
        candidates=candidates,
    )


def build_chart_guide() -> str:
    """读取 charts.md 作为图表使用指南，仅在检测到图表意图时加载。"""
    return _load_md("charts.md")


def load_intent_guide(filename: str) -> str:
    """通用意图 guide 加载器：读取 md/ 目录下指定文件。"""
    return _load_md(filename)