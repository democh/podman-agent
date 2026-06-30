"""技能管理模块：基于目录的技能系统。

技能（Skill）是高于工具（Tool）的能力层：技能不增加新工具，
而是通过注入指令到 system prompt 来增强 Agent 的行为能力。

设计原则：
- 不侵入 Tool / ToolRegistry 体系
- 每个技能是一个目录，包含 SKILL.md 主文件，支持热加载
- 启用/禁用不影响代码，仅影响 prompt 注入
- 每个技能包含：元数据（frontmatter）+ 指令正文

目录结构：
    skills/
      skill-name/
        SKILL.md              # 主技能定义文件（必需）
        mcp_tool.json         # MCP 兼容的工具定义（可选）
        references/           # 参考材料（可选）
          reference.md
          forms.md
        resources/            # 附加资源（可选）
          template.xlsx
          data.json
        scripts/              # 可执行脚本（可选）
          main.py
          helper.py

SKILL.md 文件格式：
    ---
    name: code-review
    description: 代码审查技能
    enabled: true
    triggers: 审查,review,代码质量
    ---

    # 代码审查指令

    当用户请求代码审查时，按以下标准检查...
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

SKILL_FILE = "SKILL.md"


def _slugify(name: str) -> str:
    """将名称转为安全的文件名。"""
    slug = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "untitled"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """解析 YAML frontmatter（简单 key: value 格式，支持引号值）。"""
    meta: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    value = value.strip()
                    # 去除包裹的引号（单引号或双引号）
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    meta[key.strip()] = value
            body = parts[2].strip()

    return meta, body


# 已知的 frontmatter 字段（其余字段存入 extra_meta 保留）
_KNOWN_META = {"name", "description", "enabled", "triggers", "created", "updated"}


@dataclass
class Skill:
    """单个技能的数据模型。"""
    name: str
    description: str = ""
    enabled: bool = True
    triggers: list[str] = field(default_factory=list)
    instructions: str = ""
    file_path: Path | None = None
    dir_path: Path | None = None
    created: str = ""
    updated: str = ""
    extra_meta: dict[str, str] = field(default_factory=dict)

    @property
    def trigger_str(self) -> str:
        return ", ".join(self.triggers)

    @property
    def has_references(self) -> bool:
        """是否有参考材料目录。"""
        return self.dir_path is not None and (self.dir_path / "references").is_dir()

    @property
    def has_resources(self) -> bool:
        """是否有附加资源目录。"""
        return self.dir_path is not None and (self.dir_path / "resources").is_dir()

    @property
    def has_scripts(self) -> bool:
        """是否有可执行脚本目录。"""
        return self.dir_path is not None and (self.dir_path / "scripts").is_dir()

    def list_resources(self) -> list[str]:
        """列出技能目录下所有子目录中的附加文件。

        扫描所有子目录（不仅限于 references/resources/scripts），
        递归收集文件路径（相对于技能目录）。
        """
        if not self.dir_path:
            return []
        files: list[str] = []
        for item in sorted(self.dir_path.iterdir()):
            if item.is_dir():
                for f in sorted(item.rglob("*")):
                    if f.is_file():
                        rel = f.relative_to(self.dir_path).as_posix()
                        files.append(rel)
        return files

    def to_summary(self) -> dict:
        """返回摘要信息（用于列表展示）。"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "triggers": self.triggers,
            "updated": self.updated,
        }


class SkillManager:
    """技能管理引擎：加载、启用/禁用、注入指令。"""

    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, Skill] = {}
        self.reload()

    def reload(self) -> None:
        """重新加载所有技能（热更新）。

        每个技能是 skills_dir 下的一个子目录，包含 skill.md 文件。
        """
        self._skills.clear()
        for d in sorted(self.skills_dir.iterdir()):
            if not d.is_dir():
                continue
            skill_file = d / SKILL_FILE
            if not skill_file.exists():
                continue
            skill = self._load_file(skill_file)
            if skill:
                self._skills[skill.name] = skill

    def _load_file(self, path: Path) -> Skill | None:
        """从 SKILL.md 文件加载单个技能。"""
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            name = meta.get("name", path.stem)
            triggers_raw = meta.get("triggers", "")
            triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()]
            # 保留未知字段（如 license）
            extra = {k: v for k, v in meta.items() if k not in _KNOWN_META}
            return Skill(
                name=name,
                description=meta.get("description", ""),
                enabled=meta.get("enabled", "true").strip().lower() in {"true", "1", "yes", "on"},
                triggers=triggers,
                instructions=body,
                file_path=path,
                dir_path=path.parent,
                created=meta.get("created", ""),
                updated=meta.get("updated", ""),
                extra_meta=extra,
            )
        except Exception:
            return None

    def _save_skill(self, skill: Skill) -> None:
        """将技能保存到目录中的 SKILL.md 文件，保留额外 frontmatter 字段。"""
        lines = [
            "---",
            f"name: {skill.name}",
            f"description: {skill.description}",
            f"enabled: {'true' if skill.enabled else 'false'}",
            f"triggers: {', '.join(skill.triggers)}",
        ]
        # 保留额外字段（如 license）
        for k, v in skill.extra_meta.items():
            lines.append(f"{k}: {v}")
        if not skill.created:
            skill.created = datetime.now().isoformat(timespec="seconds")
        skill.updated = datetime.now().isoformat(timespec="seconds")
        lines.append(f"created: {skill.created}")
        lines.append(f"updated: {skill.updated}")
        lines.append("---\n")

        text = "\n".join(lines) + "\n" + skill.instructions.strip() + "\n"
        skill_dir = self.skills_dir / _slugify(skill.name)
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / SKILL_FILE
        path.write_text(text, encoding="utf-8")
        skill.file_path = path

    # ── 查询接口 ──

    def list_skills(self) -> list[Skill]:
        """返回所有技能列表。"""
        return list(self._skills.values())

    def list_summary(self) -> str:
        """返回所有技能的文本摘要。"""
        skills = self.list_skills()
        if not skills:
            return "(技能库为空)"
        lines = []
        for s in skills:
            mark = "●" if s.enabled else "○"
            lines.append(f"{mark} {s.name} — {s.description} (triggers: {s.trigger_str or '无'})")
        return "\n".join(lines)

    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能。"""
        return self._skills.get(name)

    def get_skill_detail(self, name: str) -> str:
        """返回指定技能的详细信息。"""
        skill = self._skills.get(name)
        if not skill:
            return f"Error: 技能 '{name}' 不存在"
        lines = [
            f"名称: {skill.name}",
            f"描述: {skill.description}",
            f"状态: {'启用' if skill.enabled else '禁用'}",
            f"触发词: {skill.trigger_str or '无'}",
        ]
        # 显示额外字段（如 license）
        for k, v in skill.extra_meta.items():
            lines.append(f"{k}: {v}")
        if skill.updated:
            lines.append(f"更新: {skill.updated}")
        resources = skill.list_resources()
        if resources:
            lines.append(f"附加文件: {', '.join(resources)}")
        lines.extend(["", "─" * 40, "", skill.instructions])
        return "\n".join(lines)

    # ── 管理接口 ──

    def enable(self, name: str) -> str:
        """启用指定技能。"""
        skill = self._skills.get(name)
        if not skill:
            return f"Error: 技能 '{name}' 不存在"
        if skill.enabled:
            return f"技能 '{name}' 已处于启用状态"
        skill.enabled = True
        self._save_skill(skill)
        return f"已启用技能: {name}"

    def disable(self, name: str) -> str:
        """禁用指定技能。"""
        skill = self._skills.get(name)
        if not skill:
            return f"Error: 技能 '{name}' 不存在"
        if not skill.enabled:
            return f"技能 '{name}' 已处于禁用状态"
        skill.enabled = False
        self._save_skill(skill)
        return f"已禁用技能: {name}"

    def create(
        self,
        name: str,
        description: str,
        instructions: str,
        triggers: str = "",
    ) -> str:
        """创建新技能。"""
        if name in self._skills:
            return f"Error: 技能 '{name}' 已存在"
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]
        skill = Skill(
            name=name,
            description=description,
            enabled=True,
            triggers=trigger_list,
            instructions=instructions,
        )
        self._save_skill(skill)
        self._skills[name] = skill
        return f"已创建技能: {name}"

    def delete(self, name: str) -> str:
        """删除指定技能（连同目录）。"""
        skill = self._skills.get(name)
        if not skill:
            return f"Error: 技能 '{name}' 不存在"
        if skill.file_path and skill.file_path.parent != self.skills_dir:
            shutil.rmtree(skill.file_path.parent, ignore_errors=True)
        del self._skills[name]
        return f"已删除技能: {name}"

    # ── 指令注入 ──

    def get_active_instructions(self) -> str:
        """获取所有已启用技能的指令文本，用于注入 system prompt。

        如果没有已启用的技能，返回空字符串。
        """
        active = [s for s in self._skills.values() if s.enabled and s.instructions.strip()]
        if not active:
            return ""

        parts = ["# 已启用技能\n"]
        for skill in active:
            parts.append(f"## {skill.name}")
            if skill.description:
                parts.append(f"（{skill.description}）")
            parts.append("")
            parts.append(skill.instructions.strip())
            # 提示可用的附加资源
            resources = skill.list_resources()
            if resources:
                parts.append("")
                parts.append(f"> 附加文件: {', '.join(resources)}（可用 read_file 读取）")
            parts.append("")

        return "\n".join(parts)

    def count(self) -> int:
        """返回技能总数。"""
        return len(self._skills)

    def active_count(self) -> int:
        """返回已启用技能数。"""
        return sum(1 for s in self._skills.values() if s.enabled)