"""Web 界面后端：基于 FastAPI + WebSocket 提供流式聊天服务。

启动方式：
    uv run podman-agent --web [--host 0.0.0.0] [--port 8000]

WebSocket 协议：
    客户端 -> 服务端:
        {"type": "message", "content": "用户输入"}
        {"type": "stop"}
        {"type": "reset"}
        {"type": "compress"}
        {"type": "info"}
        {"type": "confirm", "request_id": "...", "decision": "approve"|"reject"}
    服务端 -> 客户端:
        {"type": "reasoning_delta", "content": "..."}
        {"type": "content_delta", "content": "..."}
        {"type": "stream_end"}
        {"type": "reasoning", "content": "..."}
        {"type": "usage", "prompt_tokens": N, ...}
        {"type": "warning", "content": "..."}
        {"type": "token_warning", "total_tokens": N, "threshold": N, "usage_pct": N, "message": "..."}
        {"type": "tool_call", "name": "...", "args": {...}}
        {"type": "tool_result", "name": "...", "result": "...", "preview": "..."}
        {"type": "separator"}
        {"type": "context_compressed", "compressed": true, "before_messages": N, "after_messages": N, ...}
        {"type": "done", "content": "..."}
        {"type": "error", "content": "..."}
        {"type": "file_ready", "path": "...", "filename": "...", "size": N, "description": "..."}
        {"type": "confirmation_request", "tool_name": "...", "args": {...}, "reason": "...", "request_id": "..."}
        {"type": "info", "model": "...", "workspace": "...", "stream": true, ...}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from ..config import Config
from ..agent import Agent
from ..skill import SkillManager
from ..tool import ToolRegistry, register_builtin, register_web_tools
from ..tool.filesystem import ShareFileTool
from ..tool.code_runner import get_available_runtimes, run_code
from ..tool.document_parser import (
    get_file_type, parse_document, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE
)
from ..memory import MemoryStore
from ..memory.tools import register_memory_tools

# 结构化日志
logger = logging.getLogger("podman_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(handler)


def create_app(config: Config | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。"""
    cfg = config or Config.from_env()
    if not cfg.api_key:
        raise RuntimeError("未设置 LLM_API_KEY，请复制 .env.example 为 .env 并填写。")

    app = FastAPI(title="Podman Agent", version="0.1.0")

    # CORS：允许前端开发服务器访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 共享的技能管理器（操作 workspace/skills/ 目录）
    shared_skills = SkillManager(os.path.join(os.getcwd(), "skills"))

    @app.get("/.well-known/appspecific/com.chrome.devtools.json")
    async def chrome_devtools_config():
        """Chrome DevTools 探测请求，返回空 JSON 避免日志噪报。"""
        return {"name": "Podman Agent"}

    @app.get("/api/download")
    async def download_file(path: str):
        """下载工作空间内的文件。

        Args:
            path: 相对于工作空间的文件路径
        """
        workspace = os.path.normpath(os.getcwd())
        full_path = os.path.normpath(os.path.join(workspace, path))
        # 防止路径穿越
        if not full_path.startswith(workspace + os.sep) and full_path != workspace:
            raise HTTPException(status_code=403, detail="路径越界")
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        return FileResponse(
            full_path,
            filename=os.path.basename(full_path),
            media_type="application/octet-stream",
        )

    @app.get("/api/info")
    async def api_info() -> dict[str, Any]:
        """返回当前配置信息（不含 API key）。"""
        return {
            "model": cfg.model,
            "base_url": cfg.base_url,
            "stream": cfg.stream,
            "enable_thinking": cfg.enable_thinking,
            "max_iterations": cfg.max_iterations,
        }

    @app.get("/api/tools")
    async def list_tools() -> dict[str, Any]:
        """返回所有可用工具名称列表（供 Settings 多选使用）。"""
        registry = ToolRegistry()
        workspace = os.path.normpath(os.getcwd())
        register_builtin(registry, workspace=workspace, config=cfg)
        registry.register(ShareFileTool(workspace))
        register_web_tools(registry)
        memories_dir = os.path.join(workspace, "memories")
        mem = MemoryStore(memories_dir)
        register_memory_tools(registry, mem)
        return {"tools": list(registry._tools.keys())}

    @app.get("/api/runtimes")
    async def list_runtimes() -> dict[str, Any]:
        """返回本地已安装的语言运行时列表。"""
        return {"runtimes": get_available_runtimes()}

    @app.post("/api/run-code")
    async def api_run_code(body: dict[str, Any]) -> dict[str, Any]:
        """执行代码片段并返回结果。"""
        language = body.get("language", "")
        code = body.get("code", "")
        if not language or not code:
            return {"success": False, "error": "缺少 language 或 code 参数"}
        result = await asyncio.to_thread(run_code, language, code)
        return result

    @app.get("/api/settings")
    async def get_settings() -> dict[str, Any]:
        """返回当前所有可配置项（分组）。"""
        return cfg.to_settings()

    @app.post("/api/settings")
    async def update_settings(body: dict[str, Any]) -> dict[str, Any]:
        """更新配置并持久化到 .env。body 为环境变量名 -> 值的扁平字典。"""
        changes = body.get("changes", {})
        if not changes:
            return {"updated": [], "message": "无变更"}
        updated = cfg.update(changes)
        logger.info(f"配置已更新: {updated}")
        return {"updated": updated, "settings": cfg.to_settings()}

    # ── 文件上传与解析 REST API ──

    @app.post("/api/upload")
    async def upload_files(files: list[UploadFile] = File(...)) -> dict[str, Any]:
        """上传文件到 workspace/download/ 目录。

        限制：
        - 最多 10 个文件
        - 每个文件不超过 10MB
        - 支持的文件类型：Office/PDF/文本
        """
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="最多上传 10 个文件")

        workspace = os.path.normpath(os.getcwd())
        download_dir = os.path.join(workspace, "download")
        os.makedirs(download_dir, exist_ok=True)

        results: list[dict[str, Any]] = []
        errors: list[str] = []

        for file in files:
            filename = file.filename or "unknown"
            file_type = get_file_type(filename)

            if not file_type:
                errors.append(f"{filename}: 不支持的文件类型")
                continue

            # 读取文件内容
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                errors.append(f"{filename}: 文件过大 ({len(content) / 1024 / 1024:.1f}MB > 10MB)")
                continue

            # 保存文件
            file_path = os.path.join(download_dir, filename)
            # 处理重名
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(download_dir, f"{base}_{counter}{ext}")
                counter += 1
            actual_filename = os.path.basename(file_path)

            with open(file_path, "wb") as f:
                f.write(content)

            # 解析文档为 Markdown
            markdown_content = ""
            try:
                markdown_content = parse_document(file_path, actual_filename)
            except Exception as e:
                logger.warning(f"文档解析失败: {actual_filename}, 错误: {e}")
                markdown_content = f"（解析失败: {e}）"

            results.append({
                "filename": actual_filename,
                "path": f"download/{actual_filename}",
                "size": len(content),
                "type": file_type,
                "markdown": markdown_content,
            })

        return {
            "uploaded": results,
            "errors": errors,
            "total": len(results),
        }

    @app.get("/api/files")
    async def list_files() -> dict[str, Any]:
        """列出 workspace/download/ 目录下的所有文件。"""
        workspace = os.path.normpath(os.getcwd())
        download_dir = os.path.join(workspace, "download")

        if not os.path.isdir(download_dir):
            return {"files": [], "total": 0}

        files: list[dict[str, Any]] = []
        for name in sorted(os.listdir(download_dir)):
            file_path = os.path.join(download_dir, name)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    "filename": name,
                    "path": f"download/{name}",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": get_file_type(name) or "unknown",
                })

        return {"files": files, "total": len(files)}

    @app.post("/api/files/parse")
    async def parse_file(body: dict[str, Any]) -> dict[str, Any]:
        """解析指定文件为 Markdown。"""
        path = body.get("path", "")
        if not path:
            raise HTTPException(status_code=400, detail="缺少 path 参数")

        workspace = os.path.normpath(os.getcwd())
        full_path = os.path.normpath(os.path.join(workspace, path))

        # 防止路径穿越
        if not full_path.startswith(workspace + os.sep):
            raise HTTPException(status_code=403, detail="路径越界")
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        filename = os.path.basename(full_path)
        try:
            markdown = parse_document(full_path, filename)
            return {"success": True, "markdown": markdown, "filename": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 技能管理 REST API ──

    @app.get("/api/skills")
    async def list_skills() -> dict[str, Any]:
        """列出所有技能。"""
        shared_skills.reload()
        return {
            "skills": [s.to_summary() for s in shared_skills.list_skills()],
            "total": shared_skills.count(),
            "active": shared_skills.active_count(),
        }

    @app.get("/api/skills/{name}")
    async def get_skill(name: str) -> dict[str, Any]:
        """获取技能详情。"""
        skill = shared_skills.get_skill(name)
        if not skill:
            return {"error": f"技能 '{name}' 不存在"}
        return {
            "name": skill.name,
            "description": skill.description,
            "enabled": skill.enabled,
            "triggers": skill.triggers,
            "instructions": skill.instructions,
            "updated": skill.updated,
        }

    @app.post("/api/skills")
    async def create_skill(body: dict[str, Any]) -> dict[str, Any]:
        """创建新技能。"""
        result = shared_skills.create(
            name=body.get("name", ""),
            description=body.get("description", ""),
            instructions=body.get("instructions", ""),
            triggers=body.get("triggers", ""),
        )
        return {"result": result}

    @app.post("/api/skills/{name}/enable")
    async def enable_skill(name: str) -> dict[str, Any]:
        """启用技能。"""
        return {"result": shared_skills.enable(name)}

    @app.post("/api/skills/{name}/disable")
    async def disable_skill(name: str) -> dict[str, Any]:
        """禁用技能。"""
        return {"result": shared_skills.disable(name)}

    @app.delete("/api/skills/{name}")
    async def delete_skill(name: str) -> dict[str, Any]:
        """删除技能。"""
        return {"result": shared_skills.delete(name)}

    @app.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket) -> None:
        """支持心跳检测、结构化日志的 WebSocket 聊天端点。"""
        await ws.accept()
        logger.info("WebSocket 连接已建立")

        loop = asyncio.get_event_loop()
        last_pong = time.time()
        HEARTBEAT_INTERVAL = 30  # 秒
        HEARTBEAT_TIMEOUT = 90  # 秒

        # 异步事件队列：非阻塞发送，避免 Agent 线程因网络慢而卡死
        event_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=1024)

        async def _event_sender() -> None:
            """后台协程：从队列取出事件并发送给前端。"""
            try:
                while True:
                    payload = await event_queue.get()
                    if payload is None:
                        break  # 收到终止信号
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        break  # 连接已关闭
            except asyncio.CancelledError:
                pass

        sender_task = asyncio.create_task(_event_sender())

        # 心跳检测协程
        async def _heartbeat() -> None:
            """ping/pong 心跳，检测死连接。"""
            nonlocal last_pong
            try:
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    if time.time() - last_pong > HEARTBEAT_TIMEOUT:
                        logger.warning("心跳超时，关闭连接")
                        await ws.close(code=1001, reason="heartbeat timeout")
                        return
                    try:
                        await ws.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        return
            except asyncio.CancelledError:
                pass

        heartbeat_task = asyncio.create_task(_heartbeat())

        def on_event(event: dict[str, Any]) -> None:
            """Agent 事件回调：将事件放入异步队列，不阻塞 Agent 工作线程。"""
            try:
                payload = json.dumps(event, ensure_ascii=False, default=str)
                loop.call_soon_threadsafe(event_queue.put_nowait, payload)
            except asyncio.QueueFull:
                pass  # 队列满时丢弃（客户端消费太慢）
            except Exception:
                pass

        agent = Agent(cfg, on_event=on_event)
        logger.info(f"Agent 初始化完成: model={cfg.model}, workspace={agent.workspace}")
        await ws.send_text(json.dumps({
            "type": "info",
            "model": cfg.model,
            "workspace": agent.workspace,
            "stream": cfg.stream,
            "enable_thinking": cfg.enable_thinking,
            "tools": [t.name for t in agent.registry._tools.values()],
            "skills": [s.to_summary() for s in agent.skills.list_skills()],
        }, ensure_ascii=False))

        agent_task: asyncio.Task | None = None

        async def _run_agent(content: str) -> None:
            """在线程池中运行 Agent，不阻塞 WebSocket 消息循环。"""
            try:
                await asyncio.to_thread(agent.run, content)
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    await ws.send_text(json.dumps(
                        {"type": "error", "content": str(e)}, ensure_ascii=False
                    ))
                except Exception:
                    pass  # 连接已关闭

        try:
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type", "message")

                # 心跳响应
                if msg_type == "pong":
                    last_pong = time.time()
                    continue

                if msg_type == "reset":
                    if agent_task and not agent_task.done():
                        await ws.send_text(json.dumps(
                            {"type": "error", "content": "Agent 正在处理中，无法重置"},
                            ensure_ascii=False,
                        ))
                        continue
                    agent.reset()
                    await ws.send_text(json.dumps(
                        {"type": "reset_ok"}, ensure_ascii=False
                    ))
                    continue

                if msg_type == "stop":
                    if agent_task and not agent_task.done():
                        agent.stop()
                        await ws.send_text(json.dumps(
                            {"type": "info", "content": "已请求停止"},
                            ensure_ascii=False,
                        ))
                    continue

                if msg_type == "compress":
                    # 手动压缩上下文（不依赖 Agent 任务状态，可独立调用）
                    if agent_task and not agent_task.done():
                        await ws.send_text(json.dumps(
                            {"type": "error", "content": "Agent 正在运行中，请等待完成后再压缩"},
                            ensure_ascii=False,
                        ))
                        continue
                    result = await asyncio.to_thread(agent.compress_context)
                    await ws.send_text(json.dumps(
                        {"type": "compress_result", **result},
                        ensure_ascii=False,
                    ))
                    continue

                if msg_type == "confirm":
                    # Human-in-the-Loop: 转发用户确认/拒绝决策到 Agent
                    request_id = data.get("request_id", "")
                    decision = data.get("decision", "reject")
                    agent.handle_confirmation(request_id, decision)
                    continue

                if msg_type == "info":
                    await ws.send_text(json.dumps({
                        "type": "info",
                        "model": cfg.model,
                        "workspace": agent.workspace,
                        "stream": cfg.stream,
                        "enable_thinking": cfg.enable_thinking,
                        "total_tokens": agent._total_tokens,
                        "skills": [s.to_summary() for s in agent.skills.list_skills()],
                    }, ensure_ascii=False))
                    continue

                if msg_type == "skill_list":
                    agent.skills.reload()
                    await ws.send_text(json.dumps({
                        "type": "skill_list",
                        "skills": [s.to_summary() for s in agent.skills.list_skills()],
                    }, ensure_ascii=False))
                    continue

                if msg_type == "skill_enable":
                    result = agent.skills.enable(data.get("name", ""))
                    await ws.send_text(json.dumps({
                        "type": "skill_updated",
                        "result": result,
                    }, ensure_ascii=False))
                    continue

                if msg_type == "skill_disable":
                    result = agent.skills.disable(data.get("name", ""))
                    await ws.send_text(json.dumps({
                        "type": "skill_updated",
                        "result": result,
                    }, ensure_ascii=False))
                    continue

                if msg_type == "memory_list":
                    result = agent.memory.list_all(exclude_conversations=True)
                    await ws.send_text(json.dumps({
                        "type": "memory_list_result",
                        "result": result,
                    }, ensure_ascii=False))
                    continue

                if msg_type == "conversation_recent":
                    days = data.get("days", 2)
                    result = agent.memory.read_recent_conversations(days)
                    await ws.send_text(json.dumps({
                        "type": "conversation_history",
                        "result": result,
                    }, ensure_ascii=False))
                    continue

                if msg_type != "message":
                    continue

                user_content = data.get("content", "").strip()
                if not user_content:
                    continue

                # 处理上传文件：将解析的 Markdown 内容拼接到用户消息前
                files = data.get("files") or []
                if files:
                    file_sections = []
                    for f in files:
                        filename = f.get("filename", "unknown")
                        markdown = f.get("markdown", "").strip()
                        if markdown:
                            file_sections.append(f"## 文件: {filename}\n\n{markdown}")
                    if file_sections:
                        files_content = "\n\n---\n\n".join(file_sections)
                        user_content = f"# 用户上传的文件\n\n{files_content}\n\n---\n\n## 用户消息\n\n{user_content}"

                # 防止并发：上一个任务还在运行时拒绝新请求
                if agent_task and not agent_task.done():
                    await ws.send_text(json.dumps(
                        {"type": "error", "content": "Agent 正在处理中，请等待当前任务完成"},
                        ensure_ascii=False,
                    ))
                    continue

                # 后台任务运行 Agent
                logger.info(f"Agent 开始处理: {user_content[:50]}...")
                agent_task = asyncio.create_task(_run_agent(user_content))

        except WebSocketDisconnect:
            logger.info("WebSocket 连接断开")
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"WebSocket 异常: {e}")
        finally:
            # 停止心跳和事件发送协程
            heartbeat_task.cancel()
            await event_queue.put(None)
            sender_task.cancel()
            if agent_task and not agent_task.done():
                agent_task.cancel()
            agent.close()
            logger.info("WebSocket 会话清理完成")

    return app