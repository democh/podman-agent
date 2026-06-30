"""Prompt 自适应优化：基于累积指标动态调整 system prompt。

不修改 md 源文件，而是生成「进化补丁」追加到 system prompt 末尾。
补丁基于工具成功率、失败模式、历史经验自动生成。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .metrics import MetricsCollector

logger = logging.getLogger(__name__)

# 置信度阈值：低于此值的补丁不会被应用
_CONFIDENCE_THRESHOLD = 0.7


class PromptAdapter:
    """Prompt 自适应引擎：基于累积指标生成动态提示词补丁。"""

    def __init__(self, base_dir: str | Path, metrics: "MetricsCollector") -> None:
        self._base_dir = Path(base_dir) / ".evolution"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._adaptations_file = self._base_dir / "adaptations.json"
        self._metrics = metrics
        # 加载已有补丁
        self._patches: list[dict] = []
        self._load_adaptations()

    # ── 公开接口 ──────────────────────────────────────────

    def get_adaptations(self) -> str:
        """生成当前有效的 prompt 补丁文本（追加到 system prompt 末尾）。"""
        # 1. 从预存补丁中筛选高置信度的
        static_patches = self._get_static_patches()

        # 2. 从实时指标中动态生成建议
        dynamic_patches = self._generate_dynamic_patches()

        all_patches = static_patches + dynamic_patches
        if not all_patches:
            return ""

        lines = ["\n# 进化适配（基于历史表现自动生成）\n"]
        for patch in all_patches[:8]:  # 最多 8 条
            lines.append(f"- {patch}")

        return "\n".join(lines)

    def add_patch(
        self,
        trigger: str,
        content: str,
        confidence: float = 0.8,
    ) -> None:
        """添加一条新补丁规则。"""
        patch = {
            "trigger": trigger,
            "content": content,
            "confidence": confidence,
            "created": datetime.now().isoformat(timespec="seconds"),
            "applied_count": 0,
        }
        self._patches.append(patch)
        self._save_adaptations()
        logger.info(f"[进化] 新增 prompt 补丁: {trigger}")

    def refresh_patches(self) -> None:
        """基于最新指标刷新补丁列表（定期任务调用）。"""
        stats = self._metrics.get_all_stats()
        new_patches = []

        for tool_name, tool_stats in stats.items():
            if tool_stats.total_calls < 5:
                continue  # 样本太少

            # 高失败率工具 -> 生成避坑提示
            if tool_stats.success_rate < 0.7:
                top_error = ""
                if tool_stats.common_errors:
                    top_error = max(
                        tool_stats.common_errors,
                        key=tool_stats.common_errors.get,  # type: ignore
                    )
                trigger = f"{tool_name} 成功率低于 70%"
                content = self._generate_tool_advice(tool_name, tool_stats.success_rate, top_error)
                if not self._patch_exists(trigger):
                    new_patches.append({
                        "trigger": trigger,
                        "content": content,
                        "confidence": min(0.9, 0.5 + tool_stats.total_calls * 0.05),
                        "created": datetime.now().isoformat(timespec="seconds"),
                        "applied_count": 0,
                    })

        if new_patches:
            self._patches.extend(new_patches)
            self._save_adaptations()
            logger.info(f"[进化] 刷新补丁：新增 {len(new_patches)} 条")

    # ── 内部实现 ──────────────────────────────────────────

    def _get_static_patches(self) -> list[str]:
        """从预存补丁中获取高置信度内容。"""
        results = []
        for patch in self._patches:
            if patch.get("confidence", 0) >= _CONFIDENCE_THRESHOLD:
                results.append(patch["content"])
                patch["applied_count"] = patch.get("applied_count", 0) + 1
        return results

    def _generate_dynamic_patches(self) -> list[str]:
        """基于实时指标动态生成建议（不持久化）。"""
        patches = []
        stats = self._metrics.get_all_stats()

        for tool_name, tool_stats in stats.items():
            if tool_stats.total_calls < 3:
                continue

            # 连续失败 pattern
            if tool_stats.failures >= 3 and tool_stats.success_rate < 0.5:
                advice = self._generate_tool_advice(
                    tool_name, tool_stats.success_rate, ""
                )
                patches.append(advice)

        return patches[:3]  # 最多 3 条动态建议

    def _generate_tool_advice(
        self, tool_name: str, success_rate: float, top_error: str
    ) -> str:
        """生成工具使用建议文本。"""
        rate_str = f"{success_rate:.0%}"
        base = f"**{tool_name}** 历史成功率 {rate_str}，使用时需格外注意"

        advice_map = {
            "edit_file": "：调用前务必先 read_file 确认 old_text 内容精确匹配",
            "write_file": "：确认目标路径正确且不会意外覆盖重要文件",
            "run_shell": "：优先使用简单、可预测的命令，避免复合管道",
            "web_search": "：query 保持精简（5-10 字），避免拼接时间词",
            "grep": "：正则特殊字符需转义，路径确认存在",
        }

        suffix = advice_map.get(tool_name, "")
        if top_error:
            suffix += f"（常见错误: {top_error}）"

        return base + suffix

    def _patch_exists(self, trigger: str) -> bool:
        """检查补丁是否已存在。"""
        return any(p.get("trigger") == trigger for p in self._patches)

    def _load_adaptations(self) -> None:
        """从 JSON 文件加载补丁。"""
        if not self._adaptations_file.exists():
            return
        try:
            data = json.loads(self._adaptations_file.read_text(encoding="utf-8"))
            self._patches = data.get("patches", [])
        except (json.JSONDecodeError, OSError):
            self._patches = []

    def _save_adaptations(self) -> None:
        """保存补丁到 JSON 文件。"""
        data = {
            "last_updated": datetime.now().isoformat(timespec="seconds"),
            "patches": self._patches,
        }
        self._adaptations_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
