"""任务清单工具。"""
from __future__ import annotations

from .base import Tool


class TodoTool(Tool):
    """轻量任务清单工具：帮助模型在复杂任务中保持条理。"""

    name = "todo"
    description = (
        "管理任务清单。复杂任务开始前先用 add 添加所有步骤，再用 update 更新状态。\n"
        "- action=list: 列出所有任务\n"
        "- action=add: 添加新任务（item=任务内容）\n"
        "- action=update: 更新任务状态（item=序号从1开始，status=pending/in_progress/done）\n"
        "- action=clear: 清空所有任务\n"
        "注意：update 前必须先 add 创建任务，否则序号会超出范围。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "update", "clear"],
                "description": "操作类型",
            },
            "item": {
                "type": "string",
                "description": "add 时为任务内容；update 时为任务序号(从1开始，必须先 add)",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "done"],
                "description": "update 时的目标状态",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._todos: list[dict[str, str]] = []

    def run(self, action: str, item: str = "", status: str = "pending") -> str:  # type: ignore[override]
        if action == "list":
            if not self._todos:
                return "(任务清单为空)"
            lines = []
            for i, t in enumerate(self._todos, start=1):
                mark = {"pending": "○", "in_progress": "◑", "done": "●"}[t["status"]]
                lines.append(f"{mark} [{i}] {t['text']} ({t['status']})")
            return "\n".join(lines)
        elif action == "add":
            self._todos.append({"text": item, "status": "pending"})
            return f"已添加任务 [{len(self._todos)}]: {item}"
        elif action == "update":
            try:
                idx = int(item) - 1
            except ValueError:
                return "Error: item 应为任务序号(数字)"
            if idx < 0 or idx >= len(self._todos):
                return f"Error: 序号超出范围，当前共 {len(self._todos)} 个任务"
            self._todos[idx]["status"] = status
            return f"已更新任务 [{idx + 1}] -> {status}"
        elif action == "clear":
            self._todos.clear()
            return "已清空任务清单"
        return f"Error: 未知 action: {action}"
