"""Shell 命令执行工具。"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from .base import Tool

# Shell 命令高危关键词
_SHELL_DANGER_PATTERNS = [
    "rm -rf", "rm -r /", "rmdir /s", "del /f /s",
    "mkfs", "dd if=", "shutdown", "reboot", "halt",
    ":(){ :|:& };:",  # fork bomb
    "chmod -R 777 /", "chown -R",
    "> /dev/sd",  # disk overwrite
]


def _detect_shell() -> tuple[str, str]:
    """检测当前系统可用的最佳 shell，返回 (shell 路径, shell 名称)。"""
    system = platform.system()
    if system == "Windows":
        for candidate in ("pwsh.exe", "powershell.exe", "cmd.exe"):
            path = shutil.which(candidate)
            if path:
                name = "pwsh" if candidate == "pwsh.exe" else (
                    "powershell" if candidate == "powershell.exe" else "cmd"
                )
                return path, name
        return "cmd.exe", "cmd"
    else:
        for candidate in ("/bin/bash", "/usr/bin/bash", "/bin/sh"):
            if Path(candidate).exists():
                name = "bash" if "bash" in candidate else "sh"
                return candidate, name
        return "/bin/sh", "sh"


def check_shell_safety(command: str, blacklist: list[str] | None = None) -> str | None:
    """Shell 命令安全检测：匹配黑名单和高危模式。返回 None 表示安全。"""
    cmd_lower = command.lower().strip()
    if blacklist:
        for pattern in blacklist:
            if pattern.lower() in cmd_lower:
                return f"Error: 命令被安全策略拦截（匹配黑名单: '{pattern}'）"
    for pattern in _SHELL_DANGER_PATTERNS:
        if pattern.lower() in cmd_lower:
            return f"Error: 检测到高危命令，拒绝执行（匹配: '{pattern}'）"
    return None


class RunShellTool(Tool):
    _SHELL_PATH, _SHELL_NAME = _detect_shell()

    name = "run_shell"
    description = (
        f"在当前工作目录执行 shell 命令，返回 stdout/stderr/exit_code（60s 超时，输出超 8000 字符截断）。"
        f"当前 shell: {_SHELL_NAME} ({platform.system()})"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的命令（须匹配当前 shell 语法）"},
        },
        "required": ["command"],
    }

    def run(self, command: str) -> str:  # type: ignore[override]
        safety_err = check_shell_safety(command, getattr(self, '_blacklist', None))
        if safety_err:
            return safety_err

        if self._SHELL_NAME in ("pwsh", "powershell"):
            args = [self._SHELL_PATH, "-NoProfile", "-Command", command]
        elif self._SHELL_NAME == "cmd":
            args = [self._SHELL_PATH, "/c", command]
        else:
            args = [self._SHELL_PATH, "-c", command]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return "Error: 命令执行超时(60s)"
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

        output = (
            f"exit_code={result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
        return output if len(output) <= 8000 else output[:8000] + "\n...[已截断]"
