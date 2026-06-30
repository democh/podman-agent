"""后台定期深度分析：Agent 启动时检查并执行周期性进化任务。

分析任务：
1. 工具效能报告：统计各工具成功率、耗时、常见错误
2. Prompt 补丁刷新：基于最新统计重新生成 adaptations
3. 用户画像刷新：综合多天数据更新偏好置信度
4. 经验去重：检测相似记忆并提示合并

触发方式：启动时检查上次分析时间，超过间隔则异步执行。
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .evolver import Evolver
    from .metrics import MetricsCollector
    from .prompt_adapter import PromptAdapter
    from .user_profile import UserProfiler

logger = logging.getLogger(__name__)


class EvolutionScheduler:
    """后台进化调度器：定期执行深度分析。"""

    def __init__(
        self,
        metrics: "MetricsCollector",
        adapter: "PromptAdapter",
        profiler: "UserProfiler",
        base_dir: str | Path,
        *,
        interval_hours: int = 24,
    ) -> None:
        self._metrics = metrics
        self._adapter = adapter
        self._profiler = profiler
        self._base_dir = Path(base_dir) / ".evolution"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._base_dir / "scheduler_state.json"
        self._interval_hours = interval_hours

    # ── 公开接口 ──────────────────────────────────────────

    def maybe_run(self) -> None:
        """启动时检查是否需要执行深度分析（异步执行）。"""
        if not self._should_run():
            return
        thread = threading.Thread(target=self._deep_analysis, daemon=True)
        thread.start()

    # ── 内部实现 ──────────────────────────────────────────

    def _should_run(self) -> bool:
        """判断是否超过分析间隔。"""
        state = self._load_state()
        last_run_str = state.get("last_run")
        if not last_run_str:
            return True
        try:
            last_run = datetime.fromisoformat(last_run_str)
            return datetime.now() - last_run > timedelta(hours=self._interval_hours)
        except (ValueError, TypeError):
            return True

    def _deep_analysis(self) -> None:
        """执行深度分析（后台线程）。"""
        logger.info("[进化] 开始定期深度分析...")
        try:
            # 1. 刷新 Prompt 补丁
            self._adapter.refresh_patches()

            # 2. 生成工具效能报告
            report = self._generate_tool_report()
            if report:
                report_file = self._base_dir / "tool_report.md"
                report_file.write_text(report, encoding="utf-8")

            # 3. 更新状态
            self._save_state({"last_run": datetime.now().isoformat(timespec="seconds")})
            logger.info("[进化] 深度分析完成")

        except Exception as e:
            logger.warning(f"[进化] 深度分析失败: {e}")

    def _generate_tool_report(self) -> str:
        """生成工具效能报告（Markdown 格式）。"""
        stats = self._metrics.get_all_stats()
        if not stats:
            return ""

        lines = [
            f"# 工具效能报告",
            f"",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            "| 工具 | 调用次数 | 成功率 | 平均耗时 | 常见错误 |",
            "| --- | --- | --- | --- | --- |",
        ]

        for name, s in sorted(stats.items(), key=lambda x: x[1].total_calls, reverse=True):
            rate = f"{s.success_rate:.0%}"
            avg_ms = f"{s.avg_duration_ms:.0f}ms"
            top_err = ""
            if s.common_errors:
                top_err = max(s.common_errors, key=s.common_errors.get)  # type: ignore
            lines.append(f"| {name} | {s.total_calls} | {rate} | {avg_ms} | {top_err} |")

        lines.append("")
        lines.append("## 优化建议")
        lines.append("")

        for name, s in stats.items():
            if s.total_calls >= 5 and s.success_rate < 0.7:
                lines.append(f"- **{name}**: 成功率偏低 ({s.success_rate:.0%})，需关注常见错误模式")

        return "\n".join(lines)

    def _load_state(self) -> dict:
        """加载调度器状态。"""
        if not self._state_file.exists():
            return {}
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict) -> None:
        """保存调度器状态。"""
        self._state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
