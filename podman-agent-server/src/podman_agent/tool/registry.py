"""工具注册表：集中管理工具，提供 schema 列表与统一调用入口。"""
from __future__ import annotations

from typing import Any

from .base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("Tool.name 不能为空")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        tool = self.get(name)
        if tool is None:
            # 防御：LLM 误将 chart 代码块当作工具调用时给出纠正引导
            if name == "chart":
                return (
                    "Error: 'chart' 不是工具，不要通过工具调用它。\n"
                    "正确用法：在你的文本回复中直接输出 ```chart 代码块（Markdown 语法），"
                    "前端会自动渲染为交互式图表。不要调用任何名为 chart 的工具。"
                )
            return f"Error: 未找到工具 '{name}'"
        try:
            return tool.run(**args)
        except TypeError as e:
            return f"Error: 调用 '{name}' 参数错误: {e}"
        except Exception as e:  # noqa: BLE001
            return f"Error: 执行 '{name}' 失败: {e}"