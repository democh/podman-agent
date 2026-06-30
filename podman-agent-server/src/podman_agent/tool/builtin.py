"""内置工具注册入口：汇总各模块工具并注册到 registry。"""
from __future__ import annotations

from .registry import ToolRegistry
from .filesystem import set_workspace, ReadFileTool, WriteFileTool, EditFileTool, ShareFileTool
from .search import ListDirTool, GlobTool, GrepTool
from .shell import RunShellTool
from .task import TodoTool
from .code_runner import RunCodeTool, detect_runtimes


def register_builtin(registry: ToolRegistry, workspace: str | None = None, config=None) -> None:
    """注册所有内置工具。

    Args:
        registry: 工具注册表
        workspace: 工作空间根路径（用于路径安全检查）
        config: 配置对象（可选，用于控制 shell 工具注册）
    """
    if workspace:
        set_workspace(workspace)

    # 文件工具
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())

    # 搜索工具
    registry.register(ListDirTool())
    registry.register(GlobTool())
    registry.register(GrepTool())

    # Shell 工具：尊重安全配置
    if config and not config.allow_shell:
        pass  # 不注册 shell 工具
    else:
        shell_tool = RunShellTool()
        if config:
            shell_tool._blacklist = config.shell_blacklist
        registry.register(shell_tool)

    # 任务清单
    registry.register(TodoTool())

    # 代码执行工具
    registry.register(RunCodeTool())

    # 启动时检测本地运行时
    detect_runtimes()
