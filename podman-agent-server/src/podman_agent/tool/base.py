"""工具抽象基类：定义工具的命名、描述、参数 schema 与执行入口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    @abstractmethod
    def run(self, **kwargs: Any) -> str:
        """执行工具，统一返回字符串结果（便于回填给 LLM）。"""

    def to_openai_schema(self) -> dict[str, Any]:
        """转换为 OpenAI tool-calling 所需的 JSON Schema 描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }