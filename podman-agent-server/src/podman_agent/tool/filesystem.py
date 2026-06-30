"""文件系统工具：读取、写入、编辑文件，以及路径安全检测。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import Tool

# ── 共享常量与工具函数 ────────────────────────────────────────────

# 常见二进制扩展名，操作前做快速过滤
_BINARY_EXTENSIONS = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
})

# 工作空间引用（由 set_workspace 设置）
_workspace_root: str | None = None


def set_workspace(workspace: str) -> None:
    """设置全局工作空间根路径，供路径遍历防护使用。"""
    global _workspace_root
    _workspace_root = os.path.realpath(workspace)


def check_path_safety(path: str) -> str | None:
    """路径遍历防护：确保路径在工作空间内。返回 None 表示安全。"""
    if _workspace_root is None:
        return None  # 未设置工作空间时不限制
    real = os.path.realpath(path)
    if real.startswith(_workspace_root + os.sep) or real == _workspace_root:
        return None
    # 允许临时目录（兼容 macOS /private/tmp）
    tmp_dirs = ["/tmp", "/var/tmp", "/private/tmp", "/private/var/tmp"]
    if any(real.startswith(t) for t in tmp_dirs):
        return None
    return f"Error: 路径超出工作空间边界，拒绝访问: {path}"


def is_binary_file(path: Path) -> bool:
    """快速判断文件是否为二进制：先查扩展名，再读前 1KB 检测 NUL 字节。"""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        return b"\x00" in chunk
    except OSError:
        return False


# ── 文件工具类 ────────────────────────────────────────────────────

class ReadFileTool(Tool):
    name = "read_file"
    description = "读取指定路径文件的文本内容，可选指定起止行号读取片段"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径，可相对或绝对"},
            "start_line": {
                "type": "integer",
                "description": "起始行号（1-based），不传则从第1行开始",
            },
            "end_line": {
                "type": "integer",
                "description": "结束行号（1-based，包含），不传则读到末尾",
            },
        },
        "required": ["path"],
    }

    def run(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:  # type: ignore[override]
        safety_err = check_path_safety(path)
        if safety_err:
            return safety_err
        p = Path(path)
        if not p.exists():
            return f"Error: 文件不存在: {path}"
        if not p.is_file():
            return f"Error: 不是文件: {path}"
        if is_binary_file(p):
            return f"Error: 文件为二进制格式，无法读取文本内容: {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)
        s = max(1, start_line or 1)
        e = min(total, end_line or total)
        if s > total:
            return f"Error: 起始行 {s} 超出文件总行数 {total}"
        selected = lines[s - 1 : e]
        numbered = [f"{i:>6}→{line}" for i, line in enumerate(selected, start=s)]
        return "\n".join(numbered)


class WriteFileTool(Tool):
    name = "write_file"
    description = "向指定路径写入完整文本内容（不存在则创建父目录，存在则覆盖）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目标文件路径"},
            "content": {"type": "string", "description": "要写入的完整文本"},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:  # type: ignore[override]
        safety_err = check_path_safety(path)
        if safety_err:
            return safety_err
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"已写入 {len(content)} 字符 -> {path}"


class EditFileTool(Tool):
    name = "edit_file"
    description = "在文件中精确替换文本片段（基于 old_text 唯一匹配）。适合局部修改，避免整体覆盖"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目标文件路径"},
            "old_text": {
                "type": "string",
                "description": "要被替换的原文，必须与文件内容精确匹配（含缩进空格换行）",
            },
            "new_text": {
                "type": "string",
                "description": "替换后的新文本",
            },
            "replace_all": {
                "type": "boolean",
                "description": "是否替换全部匹配项，默认 false 仅替换第一处",
            },
        },
        "required": ["path", "old_text", "new_text"],
    }

    def run(self, path: str, old_text: str, new_text: str, replace_all: bool = False) -> str:  # type: ignore[override]
        safety_err = check_path_safety(path)
        if safety_err:
            return safety_err
        p = Path(path)
        if not p.is_file():
            return f"Error: 文件不存在: {path}"
        if is_binary_file(p):
            return f"Error: 文件为二进制格式，不支持文本替换: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        count = content.count(old_text)
        if count == 0:
            return f"Error: 未在文件中找到指定的 old_text，请检查匹配是否精确（含缩进/换行）"
        if count > 1 and not replace_all:
            return (
                f"Error: old_text 在文件中出现 {count} 次，非唯一。"
                "请提供更长上下文使其唯一，或设置 replace_all=true"
            )
        if replace_all:
            new_content = content.replace(old_text, new_text)
            replaced = count
        else:
            new_content = content.replace(old_text, new_text, 1)
            replaced = 1
        p.write_text(new_content, encoding="utf-8")
        return f"已替换 {replaced} 处 -> {path}"


class ShareFileTool(Tool):
    """向用户发送文件供下载。"""

    name = "share_file"
    description = (
        "向用户发送文件供下载。用于分享生成的文件（如 PPT、PDF、Excel、图片等）。"
        "路径相对于工作空间。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径（相对于工作空间）",
            },
            "description": {
                "type": "string",
                "description": "文件描述（可选，展示给用户）",
            },
        },
        "required": ["path"],
    }

    def __init__(self, workspace: str, on_event=None) -> None:
        self._workspace = workspace
        self._on_event = on_event

    def run(self, path: str, description: str = "", **kwargs: Any) -> str:  # type: ignore[override]
        full_path = os.path.join(self._workspace, path)
        if not os.path.isfile(full_path):
            return f"Error: 文件不存在: {path}"
        size = os.path.getsize(full_path)
        filename = os.path.basename(path)
        if self._on_event:
            self._on_event({
                "type": "file_ready",
                "path": path,
                "filename": filename,
                "size": size,
                "description": description,
            })
        size_str = (
            f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024
            else f"{size / 1024:.1f} KB" if size >= 1024
            else f"{size} B"
        )
        return f"已发送文件: {filename} ({size_str})"
