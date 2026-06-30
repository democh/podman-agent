"""用户偏好自动建模：从对话交互中提取用户隐性偏好并形成结构化画像。

偏好分两级：
- confirmed: 用户明确表达过的偏好（高置信度，直接应用）
- inferred: 系统推断的偏好（需多次一致信号才升级）

存储：workspace/memories/.evolution/user_profile.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 推断偏好升级为确认偏好的阈值
_CONFIRM_THRESHOLD = 3  # 连续推断 N 次一致才升级


class UserProfiler:
    """用户画像管理器：采集、推断、存储用户偏好。"""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir) / ".evolution"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._profile_file = self._base_dir / "user_profile.json"
        self._profile = self._load_profile()

    # ── 公开接口 ──────────────────────────────────────────

    def get_profile_summary(self) -> str:
        """生成用户画像摘要文本（注入 system prompt 用）。"""
        confirmed = self._profile.get("confirmed", {})
        if not confirmed:
            return ""

        lines = ["## 用户偏好画像\n"]
        for key, val in confirmed.items():
            lines.append(f"- {key}: {val}")

        return "\n".join(lines)

    def get_full_profile(self) -> dict[str, Any]:
        """获取完整画像数据。"""
        return dict(self._profile)

    def update_from_insight(self, insight: dict[str, Any]) -> None:
        """从进化反思结果中更新用户偏好。

        Args:
            insight: {"key": "偏好维度", "value": "偏好值", "confidence": 0.8}
        """
        key = insight.get("key", "").strip()
        value = insight.get("value", "").strip()
        confidence = insight.get("confidence", 0.5)

        if not key or not value:
            return

        if confidence >= 0.9:
            # 高置信度直接确认
            self._confirm_preference(key, value)
        else:
            # 中等置信度记为推断
            self._infer_preference(key, value)

    def set_confirmed(self, key: str, value: str) -> None:
        """用户明确表达的偏好，直接确认。"""
        self._confirm_preference(key, value)

    def update_from_conversation(
        self,
        user_input: str,
        reply: str,
        tool_calls: list[dict],
    ) -> None:
        """从对话交互中推断偏好（轻量规则，无 LLM 调用）。"""
        # 1. 语言偏好推断
        chinese_ratio = sum(1 for c in user_input if '\u4e00' <= c <= '\u9fff') / max(len(user_input), 1)
        if chinese_ratio > 0.3:
            self._infer_preference("language", "中文")
        elif chinese_ratio < 0.05 and len(user_input) > 10:
            self._infer_preference("language", "英文")

        # 2. 沟通风格推断
        if len(user_input) < 20:
            self._infer_preference("communication_style", "简洁")
        elif len(user_input) > 200:
            self._infer_preference("communication_style", "详细")

        # 3. 技术偏好推断（从工具调用中）
        for tc in tool_calls:
            args = tc.get("args", {})
            if isinstance(args, dict):
                path = str(args.get("path", ""))
                if path.endswith(".py"):
                    self._infer_preference("tech_stack", "Python")
                elif path.endswith((".ts", ".tsx")):
                    self._infer_preference("tech_stack", "TypeScript")
                elif path.endswith((".js", ".jsx")):
                    self._infer_preference("tech_stack", "JavaScript")

        # 4. 风险偏好推断
        shell_calls = [tc for tc in tool_calls if tc.get("name") == "run_shell"]
        if len(shell_calls) > 3:
            self._infer_preference("risk_tolerance", "moderate")

    # ── 内部实现 ──────────────────────────────────────────

    def _confirm_preference(self, key: str, value: str) -> None:
        """确认一个偏好（直接写入 confirmed）。"""
        confirmed = self._profile.setdefault("confirmed", {})
        old_value = confirmed.get(key)
        confirmed[key] = value
        # 清除 inferred 中的对应项
        inferred = self._profile.get("inferred", {})
        inferred.pop(key, None)
        self._save_profile()
        if old_value != value:
            logger.info(f"[进化] 确认用户偏好: {key}={value}")

    def _infer_preference(self, key: str, value: str) -> None:
        """推断一个偏好（积累到阈值后自动升级为 confirmed）。"""
        # 已经 confirmed 的不再推断
        if key in self._profile.get("confirmed", {}):
            return

        inferred = self._profile.setdefault("inferred", {})
        entry = inferred.setdefault(key, {"value": value, "count": 0, "last_seen": ""})

        if entry["value"] == value:
            entry["count"] += 1
            entry["last_seen"] = datetime.now().isoformat(timespec="seconds")
        else:
            # 值变化，重新计数
            entry["value"] = value
            entry["count"] = 1
            entry["last_seen"] = datetime.now().isoformat(timespec="seconds")

        # 达到阈值 -> 升级为 confirmed
        if entry["count"] >= _CONFIRM_THRESHOLD:
            self._confirm_preference(key, value)
        else:
            self._save_profile()

    def _load_profile(self) -> dict[str, Any]:
        """从 JSON 文件加载画像。"""
        if not self._profile_file.exists():
            return {"confirmed": {}, "inferred": {}, "created": datetime.now().isoformat(timespec="seconds")}
        try:
            return json.loads(self._profile_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"confirmed": {}, "inferred": {}, "created": datetime.now().isoformat(timespec="seconds")}

    def _save_profile(self) -> None:
        """保存画像到 JSON 文件。"""
        self._profile["updated"] = datetime.now().isoformat(timespec="seconds")
        self._profile_file.write_text(
            json.dumps(self._profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
