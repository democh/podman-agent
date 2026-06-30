"""运行时配置：从环境变量加载 LLM 与 agent 参数。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv, set_key

load_dotenv()


@dataclass
class Config:
    api_key: str
    base_url: str
    model: str
    max_iterations: int = 20
    temperature: float = 0.2
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = True
    enable_thinking: bool = False
    # Agent 行为参数
    context_token_threshold: int = 850_000
    keep_recent: int = 20
    loop_window: int = 4
    guardrails_interval: int = 5
    # Plan-Execute-Reflect 配置
    enable_planning: bool = True
    enable_reflection: bool = True
    max_retries_per_step: int = 2
    # LATS 配置（候选方案搜索）
    enable_lats: bool = False
    lats_candidates: int = 3
    # 安全策略
    allow_shell: bool = True
    shell_blacklist: list[str] = field(default_factory=lambda: [
        "rm -rf /", "rm -rf ~", "mkfs", "dd if=", "shutdown", "reboot",
        ":(){ :|:& };:",  # fork bomb
    ])
    # Human-in-the-Loop 配置
    hitl_mode: str = "risky"  # "all" | "risky" | "none"
    hitl_tools: list[str] = field(default_factory=lambda: [
        "run_shell", "write_file", "edit_file",
    ])
    # 自进化配置
    enable_evolution: bool = True
    evolution_reflect_min_tools: int = 2  # 最少工具调用数才触发反思
    evolution_analysis_interval: int = 24  # 深度分析间隔(小时)

    @classmethod
    def from_env(cls) -> "Config":
        def _opt_float(name: str) -> float | None:
            v = os.getenv(name)
            return float(v) if v else None

        def _opt_int(name: str) -> int | None:
            v = os.getenv(name)
            return int(v) if v else None

        def _bool(name: str, default: bool) -> bool:
            v = os.getenv(name)
            if v is None:
                return default
            return v.strip().lower() in {"1", "true", "yes", "on"}

        def _list(name: str, default: list[str]) -> list[str]:
            v = os.getenv(name)
            if v is None:
                return default
            return [x.strip() for x in v.split(",") if x.strip()]

        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("LLM_MODEL", "deepseek-v4-flash"),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "20")),
            temperature=float(os.getenv("TEMPERATURE", "0.2")),
            top_p=_opt_float("TOP_P"),
            max_tokens=_opt_int("MAX_TOKENS"),
            stream=_bool("STREAM", True),
            enable_thinking=_bool("ENABLE_THINKING", False),
            context_token_threshold=int(os.getenv("CONTEXT_TOKEN_THRESHOLD", "850000")),
            keep_recent=int(os.getenv("KEEP_RECENT", "20")),
            loop_window=int(os.getenv("LOOP_WINDOW", "4")),
            guardrails_interval=int(os.getenv("GUARDRAILS_INTERVAL", "5")),
            enable_planning=_bool("ENABLE_PLANNING", True),
            enable_reflection=_bool("ENABLE_REFLECTION", True),
            max_retries_per_step=int(os.getenv("MAX_RETRIES_PER_STEP", "2")),
            enable_lats=_bool("ENABLE_LATS", False),
            lats_candidates=int(os.getenv("LATS_CANDIDATES", "3")),
            allow_shell=_bool("ALLOW_SHELL", True),
            shell_blacklist=_list("SHELL_BLACKLIST", [
                "rm -rf /", "rm -rf ~", "mkfs", "dd if=", "shutdown", "reboot",
                ":(){ :|:& };:",
            ]),
            hitl_mode=os.getenv("HITL_MODE", "risky"),
            hitl_tools=_list("HITL_TOOLS", ["run_shell", "write_file", "edit_file"]),
            enable_evolution=_bool("ENABLE_EVOLUTION", True),
            evolution_reflect_min_tools=int(os.getenv("EVOLUTION_REFLECT_MIN_TOOLS", "2")),
            evolution_analysis_interval=int(os.getenv("EVOLUTION_ANALYSIS_INTERVAL", "24")),
        )

    # ── 运行时更新（前端 Settings 面板调用）──

    def to_settings(self) -> dict:
        """导出可安全发送到前端的配置（掩码 API key）。"""
        return {
            "llm": {
                "base_url": self.base_url,
                "model": self.model,
                "max_iterations": self.max_iterations,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "max_tokens": self.max_tokens,
                "stream": self.stream,
                "enable_thinking": self.enable_thinking,
            },
            "agent": {
                "context_token_threshold": self.context_token_threshold,
                "keep_recent": self.keep_recent,
                "loop_window": self.loop_window,
                "guardrails_interval": self.guardrails_interval,
            },
            "planning": {
                "enable_planning": self.enable_planning,
                "enable_reflection": self.enable_reflection,
                "max_retries_per_step": self.max_retries_per_step,
            },
            "lats": {
                "enable_lats": self.enable_lats,
                "lats_candidates": self.lats_candidates,
            },
            "security": {
                "allow_shell": self.allow_shell,
                "shell_blacklist": ",".join(self.shell_blacklist),
            },
            "hitl": {
                "hitl_mode": self.hitl_mode,
                "hitl_tools": ",".join(self.hitl_tools),
            },
            "evolution": {
                "enable_evolution": self.enable_evolution,
                "evolution_reflect_min_tools": self.evolution_reflect_min_tools,
                "evolution_analysis_interval": self.evolution_analysis_interval,
            },
        }

    def update(self, changes: dict) -> list[str]:
        """应用配置变更并持久化到 .env 文件。返回已更新的字段列表。"""
        updated: list[str] = []
        env_path = Path(os.getenv("DOTENV_PATH", ".env"))

        def _set(key: str, value: str) -> None:
            os.environ[key] = value
            if env_path.exists():
                set_key(str(env_path), key, value)

        def _to_bool(v: object) -> bool:
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in {"1", "true", "yes", "on"}

        def _to_list(v: object) -> list[str]:
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return [x.strip() for x in str(v).split(",") if x.strip()]

        _MAP: dict[str, tuple[str, object]] = {
            "LLM_BASE_URL": ("base_url", str),
            "LLM_MODEL": ("model", str),
            "MAX_ITERATIONS": ("max_iterations", int),
            "TEMPERATURE": ("temperature", float),
            "TOP_P": ("top_p", lambda v: float(v) if v not in (None, "", "null") else None),
            "MAX_TOKENS": ("max_tokens", lambda v: int(v) if v not in (None, "", "null") else None),
            "STREAM": ("stream", _to_bool),
            "ENABLE_THINKING": ("enable_thinking", _to_bool),
            "CONTEXT_TOKEN_THRESHOLD": ("context_token_threshold", int),
            "KEEP_RECENT": ("keep_recent", int),
            "LOOP_WINDOW": ("loop_window", int),
            "GUARDRAILS_INTERVAL": ("guardrails_interval", int),
            "ENABLE_PLANNING": ("enable_planning", _to_bool),
            "ENABLE_REFLECTION": ("enable_reflection", _to_bool),
            "MAX_RETRIES_PER_STEP": ("max_retries_per_step", int),
            "ENABLE_LATS": ("enable_lats", _to_bool),
            "LATS_CANDIDATES": ("lats_candidates", int),
            "ALLOW_SHELL": ("allow_shell", _to_bool),
            "SHELL_BLACKLIST": ("shell_blacklist", _to_list),
            "HITL_MODE": ("hitl_mode", str),
            "HITL_TOOLS": ("hitl_tools", _to_list),
            "ENABLE_EVOLUTION": ("enable_evolution", _to_bool),
            "EVOLUTION_REFLECT_MIN_TOOLS": ("evolution_reflect_min_tools", int),
            "EVOLUTION_ANALYSIS_INTERVAL": ("evolution_analysis_interval", int),
        }

        for env_key, raw_val in changes.items():
            if env_key == "LLM_API_KEY":
                continue
            if env_key not in _MAP:
                continue
            attr, converter = _MAP[env_key]
            try:
                new_val = converter(raw_val)  # type: ignore[operator]
            except (ValueError, TypeError):
                continue
            setattr(self, attr, new_val)
            _set(env_key, str(raw_val) if raw_val is not None else "")
            updated.append(env_key)

        return updated