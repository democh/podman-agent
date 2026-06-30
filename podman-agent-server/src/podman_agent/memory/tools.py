"""记忆系统工具：让 Agent 能够读写、搜索持久化的 Markdown 记忆文件。"""
from __future__ import annotations

from typing import Any

from .store import MemoryStore
from ..tool.base import Tool
from ..tool.registry import ToolRegistry


class MemoryListTool(Tool):
    """列出所有记忆的摘要信息。"""

    name = "memory_list"
    description = "列出记忆库中所有记忆的标题、分类、关键词与更新时间"
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, **kwargs: Any) -> str:
        return self._store.list_all()


class MemoryReadTool(Tool):
    """读取指定记忆的完整内容。"""

    name = "memory_read"
    description = "读取指定标题的记忆的完整内容（含元数据与正文）"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "记忆标题",
            },
        },
        "required": ["title"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, title: str, **kwargs: Any) -> str:
        return self._store.get(title)


class MemoryWriteTool(Tool):
    """创建新记忆。"""

    name = "memory_write"
    description = "创建一条新记忆（Markdown 文件）。若同名已存在会报错，请用 memory_update 更新"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "记忆标题（简明扼要，用于标识这条记忆）",
            },
            "content": {
                "type": "string",
                "description": "记忆正文内容（Markdown 格式）",
            },
            "category": {
                "type": "string",
                "enum": ["project", "user", "knowledge", "general"],
                "description": "记忆分类：project=项目信息, user=用户偏好, knowledge=知识经验, general=通用",
            },
            "keywords": {
                "type": "string",
                "description": "关键词列表，逗号分隔（便于后续搜索）",
            },
        },
        "required": ["title", "content"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(
        self,
        title: str,
        content: str,
        category: str = "general",
        keywords: str = "",
        **kwargs: Any,
    ) -> str:
        return self._store.add(title, content, category, keywords)


class MemorySearchTool(Tool):
    """搜索记忆库。"""

    name = "memory_search"
    description = "在记忆库中搜索，匹配标题、关键词或正文内容，返回匹配记忆与上下文片段"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或短语",
            },
        },
        "required": ["query"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, query: str, **kwargs: Any) -> str:
        return self._store.search(query)


class MemoryUpdateTool(Tool):
    """更新已有记忆的正文内容。"""

    name = "memory_update"
    description = "更新已有记忆的正文内容（完整替换，保留元数据，自动更新时间戳）"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "要更新的记忆标题",
            },
            "content": {
                "type": "string",
                "description": "新的正文内容（完整替换）",
            },
        },
        "required": ["title", "content"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, title: str, content: str, **kwargs: Any) -> str:
        return self._store.update(title, content)


class MemoryDeleteTool(Tool):
    """删除指定记忆。"""

    name = "memory_delete"
    description = "删除指定标题的记忆（不可恢复，谨慎使用）"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "要删除的记忆标题",
            },
        },
        "required": ["title"],
    }

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def run(self, title: str, **kwargs: Any) -> str:
        return self._store.delete(title)


def register_memory_tools(registry: ToolRegistry, store: MemoryStore) -> None:
    """将所有记忆工具注册到工具注册表。"""
    registry.register(MemoryListTool(store))
    registry.register(MemoryReadTool(store))
    registry.register(MemoryWriteTool(store))
    registry.register(MemorySearchTool(store))
    registry.register(MemoryUpdateTool(store))
    registry.register(MemoryDeleteTool(store))