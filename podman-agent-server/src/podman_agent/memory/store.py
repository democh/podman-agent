"""基于 Markdown 文件的记忆系统。

每条记忆为一个 .md 文件，包含 YAML frontmatter（元数据）+ 正文内容。
文件存储在 workspace/memories/ 目录下，持久化保存。

文件格式：
    ---
    title: 记忆标题
    category: project | user | knowledge | general | conversation
    keywords: 关键词1, 关键词2
    created: 2024-01-01T12:00:00
    updated: 2024-01-01T12:00:00
    ---

    记忆正文内容...

对话日志也存储在此目录中，category 为 conversation，标题格式为「对话-YYYY-MM-DD」。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def _slugify(title: str) -> str:
    """将标题转为安全的文件名：保留中文/字母/数字，空格转下划线，其他移除。"""
    # 保留中文、字母、数字、连字符
    slug = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "untitled"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 Markdown 文件的 YAML frontmatter（简单 key: value 格式）。"""
    meta: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()
            body = parts[2].strip()

    return meta, body


def _build_frontmatter(meta: dict[str, str]) -> str:
    """构建 YAML frontmatter 字符串。"""
    lines = ["---"]
    for key in ("title", "category", "keywords", "created", "updated"):
        if key in meta:
            lines.append(f"{key}: {meta[key]}")
    lines.append("---\n")
    return "\n".join(lines)


class MemoryStore:
    """基于 Markdown 文件的记忆存储引擎。"""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _memory_path(self, title: str) -> Path:
        """根据标题生成记忆文件路径。"""
        return self.base_dir / f"{_slugify(title)}.md"

    def add(
        self,
        title: str,
        content: str,
        category: str = "general",
        keywords: str = "",
    ) -> str:
        """创建新记忆。若同名记忆已存在则返回错误。"""
        path = self._memory_path(title)
        if path.exists():
            return f"Error: 记忆 '{title}' 已存在，请使用 memory_update 更新或更换标题"

        now = datetime.now().isoformat(timespec="seconds")
        meta = {
            "title": title,
            "category": category,
            "keywords": keywords,
            "created": now,
            "updated": now,
        }
        file_text = _build_frontmatter(meta) + "\n" + content.strip() + "\n"
        path.write_text(file_text, encoding="utf-8")
        return f"已创建记忆: {title} (分类: {category}, 文件: {path.name})"

    def get(self, title: str) -> str:
        """读取指定记忆的完整内容。"""
        path = self._memory_path(title)
        if not path.exists():
            return f"Error: 记忆 '{title}' 不存在"
        return path.read_text(encoding="utf-8")

    def list_all(self, exclude_conversations: bool = False) -> str:
        """列出所有记忆的摘要信息。

        Args:
            exclude_conversations: 为 True 时排除对话日志（category=conversation），
                                   用于侧边栏记忆列表只展示结构化记忆。
        """
        files = sorted(self.base_dir.glob("*.md"))
        if not files:
            return "(记忆库为空)"

        lines = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            category = meta.get("category", "general")
            if exclude_conversations and category == "conversation":
                continue
            title = meta.get("title", f.stem)
            keywords = meta.get("keywords", "")
            updated = meta.get("updated", "")
            lines.append(f"- [{category}] {title} (keywords: {keywords}, updated: {updated})")

        if not lines:
            return "(记忆库为空)"
        return "\n".join(lines)

    def search(self, query: str) -> str:
        """在记忆库中搜索：匹配标题、关键词、正文内容。"""
        query_lower = query.lower()
        files = sorted(self.base_dir.glob("*.md"))
        if not files:
            return "(记忆库为空)"

        results = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            title = meta.get("title", f.stem)
            keywords = meta.get("keywords", "")
            category = meta.get("category", "general")

            # 匹配标题、关键词或正文
            searchable = f"{title} {keywords} {body}".lower()
            if query_lower in searchable:
                # 提取匹配上下文
                idx = body.lower().find(query_lower)
                if idx >= 0:
                    start = max(0, idx - 40)
                    end = min(len(body), idx + len(query) + 60)
                    snippet = ("..." if start > 0 else "") + body[start:end] + ("..." if end < len(body) else "")
                else:
                    snippet = body[:100] + ("..." if len(body) > 100 else "")

                results.append(f"- [{category}] {title}\n  {snippet}")

        if not results:
            return f"(未找到匹配 '{query}' 的记忆)"

        return f"找到 {len(results)} 条匹配记忆:\n" + "\n".join(results)

    def update(self, title: str, content: str) -> str:
        """更新已有记忆的正文内容（保留元数据，更新 updated 时间）。"""
        path = self._memory_path(title)
        if not path.exists():
            return f"Error: 记忆 '{title}' 不存在，请先使用 memory_write 创建"

        text = path.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(text)
        meta["updated"] = datetime.now().isoformat(timespec="seconds")

        file_text = _build_frontmatter(meta) + "\n" + content.strip() + "\n"
        path.write_text(file_text, encoding="utf-8")
        return f"已更新记忆: {title}"

    def delete(self, title: str) -> str:
        """删除指定记忆。"""
        path = self._memory_path(title)
        if not path.exists():
            return f"Error: 记忆 '{title}' 不存在"
        path.unlink()
        return f"已删除记忆: {title}"

    def count(self) -> int:
        """返回记忆总数。"""
        return len(list(self.base_dir.glob("*.md")))

    # ── 对话日志 ──────────────────────────────────────────────

    def save_turn(
        self,
        user_input: str,
        reply: str,
        tool_calls: list[dict] | None = None,
        dt: datetime | None = None,
    ) -> Path:
        """保存一轮对话到当天的对话日志文件中。

        对话日志以「对话-YYYY-MM-DD」为标题，category 为 conversation，
        存储在 memories/ 目录下，与其他记忆统一管理。
        """
        dt = dt or datetime.now()
        date_str = dt.strftime("%Y-%m-%d")
        title = f"对话-{date_str}"
        path = self._memory_path(title)

        # 文件不存在时创建带 frontmatter 的头部
        if not path.exists():
            now_iso = datetime.now().isoformat(timespec="seconds")
            meta = {
                "title": title,
                "category": "conversation",
                "keywords": date_str,
                "created": now_iso,
                "updated": now_iso,
            }
            header = _build_frontmatter(meta) + "\n"
            path.write_text(header, encoding="utf-8")

        # 追加对话内容
        parts: list[str] = [
            "",
            f"## {dt.strftime('%H:%M:%S')}",
            "",
            "**用户:**",
            "",
            user_input.strip(),
            "",
        ]

        if tool_calls:
            parts.append("**工具调用:**")
            parts.append("")
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                result = tc.get("result", "")
                preview = result if len(result) <= 200 else result[:200] + "..."
                parts.append(f"- `{name}({args})` → {preview}")
            parts.append("")

        parts.append("**助手:**")
        parts.append("")
        parts.append(reply.strip())

        # 嵌入文件标记（用于历史渲染时还原文件卡片）
        if tool_calls:
            for tc in tool_calls:
                if tc.get("name") == "share_file":
                    args = tc.get("args", {})
                    fpath = str(args.get("path", "")).replace('"', "&quot;")
                    fdesc = str(args.get("description", "")).replace('"', "&quot;")
                    parts.append(f'<!--file path="{fpath}" desc="{fdesc}"-->')
                # 嵌入搜索结果标记（用于历史渲染时还原搜索卡片）
                elif tc.get("name") == "run_shell":
                    cmd = str(tc.get("args", {}).get("command", ""))
                    if "search.py" in cmd:
                        result = tc.get("result", "")
                        if result and not result.startswith("Error:"):
                            # 用 base64 编码避免 Markdown 解析干扰
                            import base64
                            encoded = base64.b64encode(result.encode("utf-8")).decode("ascii")
                            parts.append(f'<!--search {encoded}-->')

        parts.append("")
        parts.append("---")
        parts.append("")

        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(parts))

        # 更新 frontmatter 中的 updated 时间戳
        self._touch_timestamp(path)
        return path

    def read_recent_conversations(self, days: int = 2) -> str:
        """读取最近 N 个自然日内的对话记录（按文件名日期严格过滤）。"""
        from datetime import timedelta

        today = datetime.now().date()
        cutoff = today - timedelta(days=days - 1)  # 包含今天在内共 N 天

        conv_files = []
        for f in self.base_dir.glob("对话-*.md"):
            # 从文件名提取日期：对话-YYYY-MM-DD.md
            date_str = f.stem.removeprefix("对话-")
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if file_date >= cutoff:
                conv_files.append((file_date, f))

        conv_files.sort(key=lambda x: x[0])

        if not conv_files:
            return "(无对话历史)"

        parts: list[str] = []
        for _, f in conv_files:
            parts.append(f.read_text(encoding="utf-8"))
            parts.append("")
        return "\n".join(parts)

    def _touch_timestamp(self, path: Path) -> None:
        """更新记忆文件 frontmatter 中的 updated 时间戳。"""
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        meta["updated"] = datetime.now().isoformat(timespec="seconds")
        new_text = _build_frontmatter(meta) + "\n" + body + "\n"
        path.write_text(new_text, encoding="utf-8")