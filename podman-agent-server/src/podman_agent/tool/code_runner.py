"""代码执行工具：检测本地运行时环境并执行代码片段。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .base import Tool

# ── 语言运行时定义 ────────────────────────────────────────────────

@dataclass
class RuntimeInfo:
    """单个语言运行时的信息。"""
    language: str        # 语言标识（与前端 highlight.js 匹配）
    display: str         # 显示名称
    command: str         # 运行命令
    ext: str             # 文件扩展名
    compile_cmd: str | None = None  # 编译命令模板（{src} {out}）
    version: str = ""    # 检测到的版本

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "display": self.display,
            "command": self.command,
            "version": self.version,
        }


# 支持的语言列表
_RUNTIME_DEFS: list[dict] = [
    {"language": "python", "aliases": ["py"], "display": "Python", "commands": ["python3", "python"], "ext": ".py"},
    {"language": "javascript", "aliases": ["js"], "display": "Node.js", "commands": ["node"], "ext": ".js"},
    {"language": "typescript", "aliases": ["ts"], "display": "ts-node/tsx", "commands": ["tsx", "ts-node", "npx tsx"], "ext": ".ts"},
    {"language": "go", "aliases": [], "display": "Go", "commands": ["go run"], "ext": ".go"},
    {"language": "rust", "aliases": ["rs"], "display": "Rust", "commands": ["rustc"], "ext": ".rs", "compile": True},
    {"language": "java", "aliases": [], "display": "Java", "commands": ["java"], "ext": ".java"},
    {"language": "c", "aliases": [], "display": "GCC (C)", "commands": ["gcc"], "ext": ".c", "compile": True},
    {"language": "cpp", "aliases": ["c++", "cxx"], "display": "G++ (C++)", "commands": ["g++"], "ext": ".cpp", "compile": True},
    {"language": "bash", "aliases": ["sh", "shell"], "display": "Bash", "commands": ["bash"], "ext": ".sh"},
    {"language": "ruby", "aliases": ["rb"], "display": "Ruby", "commands": ["ruby"], "ext": ".rb"},
    {"language": "php", "aliases": [], "display": "PHP", "commands": ["php"], "ext": ".php"},
    {"language": "swift", "aliases": [], "display": "Swift", "commands": ["swift"], "ext": ".swift"},
    {"language": "kotlin", "aliases": ["kt"], "display": "Kotlin", "commands": ["kotlin", "kotlinc"], "ext": ".kt", "compile": True},
]

# ── 运行时检测 ────────────────────────────────────────────────────

_detected_runtimes: dict[str, RuntimeInfo] = {}
_alias_map: dict[str, str] = {}


def _get_version(cmd: str) -> str:
    """尝试获取命令版本号。"""
    try:
        # 特殊处理 'go run' 等组合命令
        base_cmd = cmd.split()[0]
        result = subprocess.run(
            [base_cmd, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        output = (result.stdout or result.stderr).strip()
        # 取第一行，截断
        first_line = output.split("\n")[0]
        return first_line[:80] if first_line else ""
    except Exception:
        return ""


def detect_runtimes() -> dict[str, RuntimeInfo]:
    """检测本地已安装的语言运行时，返回可用的运行时字典。"""
    global _detected_runtimes, _alias_map
    _detected_runtimes.clear()
    _alias_map.clear()

    for defn in _RUNTIME_DEFS:
        lang = defn["language"]
        found_cmd = None

        for cmd in defn["commands"]:
            base_cmd = cmd.split()[0]
            if shutil.which(base_cmd):
                found_cmd = cmd
                break

        if found_cmd:
            version = _get_version(found_cmd)
            runtime = RuntimeInfo(
                language=lang,
                display=defn["display"],
                command=found_cmd,
                ext=defn["ext"],
                compile_cmd=found_cmd if defn.get("compile") else None,
                version=version,
            )
            _detected_runtimes[lang] = runtime
            # 注册别名映射
            for alias in defn.get("aliases", []):
                _alias_map[alias] = lang

    return _detected_runtimes


def get_available_runtimes() -> list[dict]:
    """获取所有可用运行时列表（供 API 使用）。"""
    if not _detected_runtimes:
        detect_runtimes()
    return [rt.to_dict() for rt in _detected_runtimes.values()]


def resolve_language(lang: str) -> str | None:
    """解析语言标识，支持别名。返回规范化语言名或 None。"""
    if not _detected_runtimes:
        detect_runtimes()
    lang_lower = lang.lower().strip()
    if lang_lower in _detected_runtimes:
        return lang_lower
    if lang_lower in _alias_map:
        return _alias_map[lang_lower]
    return None


# ── 代码执行 ────────────────────────────────────────────────────

def run_code(language: str, code: str, timeout: int = 30) -> dict:
    """执行代码片段，返回结构化结果。

    Returns:
        {"success": bool, "stdout": str, "stderr": str, "exit_code": int, "error": str}
    """
    resolved = resolve_language(language)
    if not resolved:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": f"不支持或未安装的语言: {language}",
        }

    runtime = _detected_runtimes[resolved]
    tmpdir = tempfile.mkdtemp(prefix="podman_agent_run_")

    try:
        src_file = os.path.join(tmpdir, f"code{runtime.ext}")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(code)

        # 构造执行命令
        if runtime.compile_cmd:
            # 需要编译的语言
            if resolved == "rust":
                out_file = os.path.join(tmpdir, "code")
                compile_result = subprocess.run(
                    ["rustc", src_file, "-o", out_file],
                    capture_output=True, text=True, timeout=timeout, cwd=tmpdir,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "stdout": compile_result.stdout[:4000],
                        "stderr": compile_result.stderr[:4000],
                        "exit_code": compile_result.returncode,
                        "error": "编译失败",
                    }
                args = [out_file]
            elif resolved in ("c", "cpp"):
                out_file = os.path.join(tmpdir, "code")
                compiler = "g++" if resolved == "cpp" else "gcc"
                compile_result = subprocess.run(
                    [compiler, src_file, "-o", out_file],
                    capture_output=True, text=True, timeout=timeout, cwd=tmpdir,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "stdout": compile_result.stdout[:4000],
                        "stderr": compile_result.stderr[:4000],
                        "exit_code": compile_result.returncode,
                        "error": "编译失败",
                    }
                args = [out_file]
            elif resolved == "java":
                # Java: javac 编译 + java 运行
                compile_result = subprocess.run(
                    ["javac", src_file],
                    capture_output=True, text=True, timeout=timeout, cwd=tmpdir,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "stdout": compile_result.stdout[:4000],
                        "stderr": compile_result.stderr[:4000],
                        "exit_code": compile_result.returncode,
                        "error": "编译失败",
                    }
                # 找到生成的 .class 文件
                class_name = Path(src_file).stem
                args = ["java", "-cp", tmpdir, class_name]
            elif resolved == "kotlin":
                jar_file = os.path.join(tmpdir, "code.jar")
                compile_result = subprocess.run(
                    ["kotlinc", src_file, "-include-runtime", "-d", jar_file],
                    capture_output=True, text=True, timeout=60, cwd=tmpdir,
                )
                if compile_result.returncode != 0:
                    return {
                        "success": False,
                        "stdout": compile_result.stdout[:4000],
                        "stderr": compile_result.stderr[:4000],
                        "exit_code": compile_result.returncode,
                        "error": "编译失败",
                    }
                args = ["java", "-jar", jar_file]
            else:
                args = [runtime.command, src_file]
        else:
            # 解释型语言
            cmd_parts = runtime.command.split()
            if resolved == "go":
                args = ["go", "run", src_file]
            elif resolved == "java":
                # Java 11+ 支持直接 java xxx.java
                args = ["java", src_file]
            else:
                args = cmd_parts + [src_file]

        # 执行
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=tmpdir,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        stdout = result.stdout[:8000] if result.stdout else ""
        stderr = result.stderr[:4000] if result.stderr else ""

        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
            "error": "",
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": f"执行超时（{timeout}s）",
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": str(e),
        }
    finally:
        # 清理临时目录
        import shutil as _shutil
        try:
            _shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ── 工具类（可供 Agent 调用） ────────────────────────────────────

class RunCodeTool(Tool):
    """执行代码片段工具。"""

    name = "run_code"
    description = (
        "在本地执行代码片段并返回结果。"
        "支持 Python、JavaScript(Node.js)、Go、Rust、Java、C/C++、Bash 等语言。"
        "代码在隔离的临时目录中执行，30s 超时。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "编程语言（python/javascript/go/rust/java/c/cpp/bash 等）",
            },
            "code": {
                "type": "string",
                "description": "要执行的代码",
            },
        },
        "required": ["language", "code"],
    }

    def run(self, language: str, code: str) -> str:  # type: ignore[override]
        result = run_code(language, code)
        if result["error"]:
            output = f"Error: {result['error']}"
            if result["stderr"]:
                output += f"\n--- stderr ---\n{result['stderr']}"
            if result["stdout"]:
                output += f"\n--- stdout ---\n{result['stdout']}"
            return output

        output = f"exit_code={result['exit_code']}\n"
        if result["stdout"]:
            output += f"--- stdout ---\n{result['stdout']}"
        if result["stderr"]:
            output += f"\n--- stderr ---\n{result['stderr']}"
        return output.strip()
