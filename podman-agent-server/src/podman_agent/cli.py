"""命令行入口：支持交互式 REPL 与 Web 界面两种模式。

用法：
    podman-agent                          # 启动交互式 REPL（默认）
    podman-agent --web                    # 启动 Web 界面
    podman-agent-server --workspace ../workspace  # 指定工作空间
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

from .agent import Agent
from .config import Config

# ANSI 颜色（Windows 10+ 终端原生支持）
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_RESET = "\033[0m"

HELP_TEXT = f"""
{_CYAN}Podman Agent 命令{_RESET}
  {_GREEN}/help{_RESET}              显示本帮助
  {_GREEN}/reset{_RESET}             清空对话上下文
  {_GREEN}/stop{_RESET}              停止当前任务（或按 Ctrl+C）
  {_GREEN}/multi{_RESET}             进入多行输入模式（空行结束）
  {_GREEN}/usage{_RESET}             查看累计 token 用量
  {_GREEN}/model{_RESET}             查看当前模型配置
  {_GREEN}/skills{_RESET}            列出所有技能
  {_GREEN}/skill on <name>{_RESET}   启用指定技能
  {_GREEN}/skill off <name>{_RESET}  禁用指定技能
  {_GREEN}/skill show <name>{_RESET} 查看技能详情
  {_GREEN}/exit{_RESET} / {_GREEN}/quit{_RESET}       退出
"""


def _print_banner(config: Config, agent: Agent) -> None:
    print(f"{_CYAN}{'=' * 50}{_RESET}")
    print(f"{_CYAN}  Podman Agent{_RESET}")
    print(f"{'=' * 50}")
    print(f"  {_DIM}模型:{_RESET}     {config.model}")
    print(f"  {_DIM}工作目录:{_RESET} {agent.workspace}")
    print(f"  {_DIM}流式:{_RESET}     {'开' if config.stream else '关'}")
    print(f"  {_DIM}思考模式:{_RESET} {'开' if config.enable_thinking else '关'}")
    print(f"  {_DIM}工具数:{_RESET}   {len(agent.registry.list_schemas())}")
    print(f"  {_DIM}技能数:{_RESET}   {agent.skills.count()} (启用 {agent.skills.active_count()})")
    print(f"  {_DIM}记忆数:{_RESET}   {agent.memory.count()}")
    print(f"{_CYAN}{'=' * 50}{_RESET}")
    print(f"输入 {_GREEN}/help{_RESET} 查看命令，{_GREEN}/exit{_RESET} 退出。\n")


def _read_multi_line() -> str:
    """多行输入模式：连续输入，空行结束。"""
    print(f"{_YELLOW}多行模式（空行结束）:{_RESET}")
    lines: list[str] = []
    while True:
        try:
            line = input("... ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def run_repl(config: Config) -> None:
    """启动交互式 REPL 模式。"""
    agent = Agent(config)
    _print_banner(config, agent)

    try:
        while True:
            try:
                user_input = input(f"{_GREEN}you>{_RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            # 内置命令
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/exit", "/quit"):
                    break
                elif cmd == "/reset":
                    agent.reset()
                    print(f"{_YELLOW}[上下文已清空]{_RESET}\n")
                elif cmd == "/help":
                    print(HELP_TEXT)
                elif cmd == "/multi":
                    text = _read_multi_line()
                    if text.strip():
                        _run_agent(agent, text)
                elif cmd == "/usage":
                    print(f"累计 total_tokens ≈ {agent._total_tokens}\n")
                elif cmd == "/model":
                    print(f"model={config.model}  base_url={config.base_url}\n")
                elif cmd == "/skills":
                    agent.skills.reload()
                    print(agent.skills.list_summary())
                    print()
                elif cmd.startswith("/skill "):
                    parts = user_input.split(None, 2)
                    if len(parts) < 3:
                        print(f"{_YELLOW}用法:{_RESET} /skill <on|off|show> <name>\n")
                    else:
                        action, skill_name = parts[1], parts[2]
                        if action == "on":
                            print(f"{agent.skills.enable(skill_name)}\n")
                        elif action == "off":
                            print(f"{agent.skills.disable(skill_name)}\n")
                        elif action == "show":
                            print(agent.skills.get_skill_detail(skill_name))
                            print()
                        else:
                            print(f"{_YELLOW}未知操作:{_RESET} {action}（支持 on/off/show）\n")
                else:
                    print(f"{_YELLOW}未知命令:{_RESET} {user_input}（输入 /help 查看）\n")
                continue

            _run_agent(agent, user_input)
    finally:
        agent.close()


def _run_agent(agent: Agent, user_input: str) -> None:
    """执行一次 agent 调用，支持 Ctrl+C 手动停止。"""
    error_holder: list[str] = []

    def _target() -> None:
        try:
            agent.run(user_input)
        except Exception as e:
            error_holder.append(str(e))

    t = threading.Thread(target=_target, daemon=True)
    t.start()

    try:
        while t.is_alive():
            t.join(timeout=0.1)
    except KeyboardInterrupt:
        agent.stop()
        print(f"\n{_YELLOW}[请求停止，等待当前操作完成...]{_RESET}")
        t.join(timeout=30)
        print(f"{_YELLOW}[已停止]{_RESET}\n")
        return

    if error_holder:
        print(f"{_YELLOW}[error]{_RESET} {error_holder[0]}\n")
        return

    # 流式模式下回复已实时打印，此处仅在非流式时补印
    if not agent.config.stream:
        # 从 messages 中取最后一条 assistant 回复
        reply = ""
        for m in reversed(agent.messages):
            if m.get("role") == "assistant" and m.get("content"):
                reply = m["content"]
                break
        if reply:
            print(f"\n{_CYAN}agent>{_RESET} {reply}\n")
    else:
        print()


def run_web(config: Config, host: str, port: int) -> None:
    """启动 Web 界面模式。"""
    try:
        import uvicorn
    except ImportError:
        print(f"{_YELLOW}Error:{_RESET} 未安装 web 依赖，请运行: uv pip install fastapi uvicorn[standard]")
        sys.exit(1)

    from .web import create_app

    app = create_app(config)

    print(f"{_CYAN}{'=' * 50}{_RESET}")
    print(f"{_CYAN}  Podman Agent - Web Mode{_RESET}")
    print(f"{'=' * 50}")
    print(f"  {_DIM}模型:{_RESET}     {config.model}")
    print(f"  {_DIM}流式:{_RESET}     {'开' if config.stream else '关'}")
    print(f"  {_DIM}思考模式:{_RESET} {'开' if config.enable_thinking else '关'}")
    print(f"  {_DIM}地址:{_RESET}     http://{host}:{port}")
    print(f"{_CYAN}{'=' * 50}{_RESET}")
    print(f"浏览器打开 {_GREEN}http://{host}:{port}{_RESET} 开始使用\n")

    uvicorn.run(app, host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Podman Agent - 最小可行编码助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--web", action="store_true",
        help="启动 Web 界面模式（默认为 REPL 交互模式）",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Web 模式监听地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Web 模式监听端口（默认 8000）",
    )
    parser.add_argument(
        "--workspace", default="../workspace",
        help="工作空间目录，所有内容在此目录下操作（默认 ../workspace）",
    )
    args = parser.parse_args()

    # 解析并切换到工作空间，所有后续操作基于此目录
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    config = Config.from_env()
    if not config.api_key:
        print(f"{_YELLOW}Error:{_RESET} 未设置 LLM_API_KEY，请复制 .env.example 为 .env 并填写。")
        sys.exit(1)

    if args.web:
        run_web(config, args.host, args.port)
    else:
        run_repl(config)


if __name__ == "__main__":
    main()