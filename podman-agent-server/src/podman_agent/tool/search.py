"""搜索工具：列目录、文件名匹配、内容搜索。"""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from .base import Tool
from .filesystem import is_binary_file


class ListDirTool(Tool):
    name = "list_dir"
    description = "列出目录下的文件与子目录（含类型标记）"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认为当前目录"},
        },
    }

    def run(self, path: str = ".") -> str:  # type: ignore[override]
        p = Path(path)
        if not p.exists():
            return f"Error: 目录不存在: {path}"
        if not p.is_dir():
            return f"Error: 不是目录: {path}"
        entries = []
        for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            tag = "[DIR] " if e.is_dir() else "[FILE]"
            entries.append(f"{tag} {e.name}")
        return "\n".join(entries) if entries else "(空目录)"


class GlobTool(Tool):
    name = "glob"
    description = "按文件名模式递归查找文件，返回匹配的路径列表"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "文件名匹配模式，如 **/*.py 或 config*.json",
            },
            "path": {
                "type": "string",
                "description": "搜索根目录，默认当前目录",
            },
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, path: str = ".") -> str:  # type: ignore[override]
        root = Path(path)
        if not root.is_dir():
            return f"Error: 不是目录: {path}"
        matches: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                if fnmatch.fnmatch(fname, pattern):
                    full = os.path.relpath(os.path.join(dirpath, fname), root)
                    matches.append(full)
        matches = sorted(set(matches))
        if not matches:
            return "(无匹配文件)"
        if len(matches) > 200:
            return "\n".join(matches[:200]) + f"\n...[共 {len(matches)} 个，已截断显示前 200]"
        return "\n".join(matches)


class GrepTool(Tool):
    name = "grep"
    description = "在文件内容中搜索正则表达式，返回匹配行及行号。支持指定文件名过滤"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "正则表达式",
            },
            "path": {
                "type": "string",
                "description": "搜索目录或单个文件，默认当前目录",
            },
            "include": {
                "type": "string",
                "description": "只搜索匹配该文件名模式的文件，如 *.py",
            },
        },
        "required": ["pattern"],
    }

    def run(self, pattern: str, path: str = ".", include: str | None = None) -> str:  # type: ignore[override]
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Error: 正则表达式无效: {e}"

        root = Path(path)
        files_to_search: list[Path] = []
        if root.is_file():
            files_to_search = [root]
        else:
            for dirpath, _dirnames, filenames in os.walk(root):
                for fname in filenames:
                    if include and not fnmatch.fnmatch(fname, include):
                        continue
                    files_to_search.append(Path(dirpath) / fname)

        results: list[str] = []
        total_matches = 0
        for fpath in files_to_search:
            if is_binary_file(fpath):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    rel = fpath.relative_to(root) if root.is_dir() else fpath.name
                    results.append(f"{rel}:{i}: {line.rstrip()}")
                    total_matches += 1
            if total_matches >= 500:
                results.append(f"...[匹配数已达 500，停止搜索]")
                break

        if not results:
            return "(无匹配)"
        return "\n".join(results)
