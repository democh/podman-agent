"""指标采集系统：记录工具调用与对话级指标，为自进化提供原始数据。

存储格式：JSONL（追加写入），按天轮转。
存储路径：workspace/memories/.evolution/metrics.jsonl
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ToolMetric:
    """单次工具调用指标。"""
    timestamp: str
    tool_name: str
    args_hash: str
    args_pattern: str
    success: bool
    duration_ms: int
    error_type: str | None = None
    context: str = ""


@dataclass
class ConversationMetric:
    """单轮对话级指标。"""
    timestamp: str
    user_input_len: int
    total_turns: int
    plan_steps: int
    success: bool
    paradigm_used: str
    total_tokens: int
    duration_s: float
    tool_calls_count: int = 0
    tool_failures: int = 0


@dataclass
class ToolStats:
    """工具使用统计（内存中维护的聚合视图）。"""
    total_calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: int = 0
    common_errors: dict[str, int] = field(default_factory=dict)
    recent_patterns: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_calls if self.total_calls > 0 else 1.0

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0


class MetricsCollector:
    """指标采集器：持久化写入 JSONL + 内存聚合统计。"""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir) / ".evolution"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._metrics_file = self._base_dir / "metrics.jsonl"
        self._conv_file = self._base_dir / "conversations.jsonl"

        # 内存聚合：工具统计 {tool_name: ToolStats}
        self._tool_stats: dict[str, ToolStats] = {}
        # 加载历史统计
        self._load_historical_stats()

    # ── 工具指标 ──────────────────────────────────────────

    def record_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: str,
        duration_ms: int,
        context: str = "",
    ) -> ToolMetric:
        """记录单次工具调用指标。"""
        success = not result.startswith("Error:")
        error_type = self._classify_error(result) if not success else None
        args_pattern = self._extract_args_pattern(tool_name, args)
        args_hash = hashlib.md5(
            json.dumps(args, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]

        metric = ToolMetric(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            tool_name=tool_name,
            args_hash=args_hash,
            args_pattern=args_pattern,
            success=success,
            duration_ms=duration_ms,
            error_type=error_type,
            context=context[:100],
        )

        # 持久化
        self._append_jsonl(self._metrics_file, asdict(metric))

        # 更新内存聚合
        stats = self._tool_stats.setdefault(tool_name, ToolStats())
        stats.total_calls += 1
        stats.total_duration_ms += duration_ms
        if success:
            stats.successes += 1
        else:
            stats.failures += 1
            if error_type:
                stats.common_errors[error_type] = stats.common_errors.get(error_type, 0) + 1
        # 保留最近 10 个参数模式
        stats.recent_patterns.append(args_pattern)
        if len(stats.recent_patterns) > 10:
            stats.recent_patterns.pop(0)

        return metric

    # ── 对话指标 ──────────────────────────────────────────

    def record_conversation(
        self,
        user_input_len: int,
        total_turns: int,
        plan_steps: int,
        success: bool,
        paradigm_used: str,
        total_tokens: int,
        duration_s: float,
        tool_calls_count: int = 0,
        tool_failures: int = 0,
    ) -> ConversationMetric:
        """记录对话级指标。"""
        metric = ConversationMetric(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            user_input_len=user_input_len,
            total_turns=total_turns,
            plan_steps=plan_steps,
            success=success,
            paradigm_used=paradigm_used,
            total_tokens=total_tokens,
            duration_s=duration_s,
            tool_calls_count=tool_calls_count,
            tool_failures=tool_failures,
        )
        self._append_jsonl(self._conv_file, asdict(metric))
        return metric

    # ── 查询接口 ──────────────────────────────────────────

    def get_tool_stats(self, tool_name: str) -> ToolStats | None:
        """获取指定工具的聚合统计。"""
        return self._tool_stats.get(tool_name)

    def get_all_stats(self) -> dict[str, ToolStats]:
        """获取所有工具的聚合统计。"""
        return dict(self._tool_stats)

    def get_tool_suggestions(self) -> str:
        """基于历史指标生成工具使用建议文本。"""
        if not self._tool_stats:
            return ""

        lines = ["## 工具使用建议（基于历史数据）\n"]
        for name, stats in sorted(
            self._tool_stats.items(),
            key=lambda x: x[1].total_calls,
            reverse=True,
        ):
            if stats.total_calls < 3:
                continue  # 样本太少，不生成建议
            rate = f"{stats.success_rate:.0%}"
            line = f"- **{name}**: 成功率 {rate} (共 {stats.total_calls} 次)"
            if stats.common_errors:
                top_error = max(stats.common_errors, key=stats.common_errors.get)  # type: ignore
                line += f"，常见失败: {top_error}"
            lines.append(line)

        return "\n".join(lines) if len(lines) > 1 else ""

    # ── 内部辅助 ──────────────────────────────────────────

    def _append_jsonl(self, path: Path, data: dict) -> None:
        """追加写入 JSONL 文件。"""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _load_historical_stats(self) -> None:
        """从历史 JSONL 加载聚合统计（启动时执行一次）。"""
        if not self._metrics_file.exists():
            return
        try:
            with open(self._metrics_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    name = record.get("tool_name", "")
                    if not name:
                        continue
                    stats = self._tool_stats.setdefault(name, ToolStats())
                    stats.total_calls += 1
                    stats.total_duration_ms += record.get("duration_ms", 0)
                    if record.get("success"):
                        stats.successes += 1
                    else:
                        stats.failures += 1
                        err = record.get("error_type")
                        if err:
                            stats.common_errors[err] = stats.common_errors.get(err, 0) + 1
        except OSError:
            pass  # 文件不可读时静默跳过

    @staticmethod
    def _classify_error(result: str) -> str:
        """从工具结果中分类错误类型。"""
        lower = result[:200].lower()
        if "not found" in lower or "不存在" in lower:
            return "not_found"
        if "permission" in lower or "权限" in lower:
            return "permission"
        if "timeout" in lower or "超时" in lower:
            return "timeout"
        if "syntax" in lower or "语法" in lower:
            return "syntax"
        if "already exists" in lower or "已存在" in lower:
            return "already_exists"
        return "other"

    @staticmethod
    def _extract_args_pattern(tool_name: str, args: dict) -> str:
        """提取参数模式摘要（去敏）。"""
        parts = []
        for key, val in args.items():
            if isinstance(val, str):
                if len(val) > 50:
                    parts.append(f"{key}={len(val)}chars")
                else:
                    # 文件路径保留扩展名
                    if "/" in val or "\\" in val:
                        ext = Path(val).suffix or "no_ext"
                        parts.append(f"{key}=*{ext}")
                    else:
                        parts.append(f"{key}={val[:20]}")
            elif isinstance(val, (int, float, bool)):
                parts.append(f"{key}={val}")
            else:
                parts.append(f"{key}=<{type(val).__name__}>")
        return ", ".join(parts) if parts else "(no args)"


def timed_execution(func, *args, **kwargs) -> tuple:
    """计时执行辅助函数，返回 (result, duration_ms)。"""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    duration_ms = int((time.perf_counter() - start) * 1000)
    return result, duration_ms
