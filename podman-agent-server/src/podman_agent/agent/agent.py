"""Agent 主循环：理解 -> 规划 -> 候选搜索 -> 执行 -> 反思，直至给出最终回复。

增强点：
- Plan-Execute-Reflect：复杂任务先拆解计划，逐步执行，每步反思评估
- LATS（Language Agent Tree Search）：每步生成多个候选方案，评估择优执行
- 上下文长度保护：超过阈值时自动压缩历史（保留 system + 最近若干轮）
- 循环检测：滑动窗口检测重复工具调用模式
- finish_reason 处理：length 截断时提示用户
- 工具指南注入 system prompt，引导模型正确使用工具
- 多轮 guardrails 定期注入，防止模型偏离约束
- on_event 回调：支持 Web/UI 层订阅事件（流式、工具调用、用量等）
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from ..config import Config
from ..core.llm import LLMClient
from ..evolution import Evolver, EvolutionScheduler, MetricsCollector, PromptAdapter, UserProfiler
from ..memory import MemoryStore
from ..memory.tools import register_memory_tools
from ..prompts import build_system_prompt, build_tools_overview
from ..prompts.intent_detector import IntentDetector
from ..skill import SkillManager
from ..tool import ToolRegistry, register_builtin, register_web_tools
from ..tool.filesystem import ShareFileTool
from ..tool.web_search import set_stop_check
from .lats import ContextManager, LatsStrategy, _estimate_tokens
from .planner import Planner

# 事件回调类型：(event_dict) -> None
OnEvent = Callable[[dict[str, Any]], None]


class Agent:
    def __init__(
        self,
        config: Config,
        workspace: str | None = None,
        on_event: OnEvent | None = None,
    ) -> None:
        self.config = config
        self.workspace = workspace or os.getcwd()
        self._on_event = on_event
        self.llm = LLMClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            enable_thinking=config.enable_thinking,
        )
        self.registry = ToolRegistry()
        register_builtin(self.registry, workspace=self.workspace, config=config)

        # 文件分享工具：需要 workspace 和事件回调
        self.registry.register(ShareFileTool(self.workspace, self._emit))

        # Web 搜索工具：联网搜索 + 正文提取
        register_web_tools(self.registry)
        set_stop_check(lambda: self._stop_requested)

        # 记忆系统：基于 MD 文件的持久化记忆，存储在 workspace/memories/
        self.memory = MemoryStore(os.path.join(self.workspace, "memories"))
        register_memory_tools(self.registry, self.memory)

        # 自进化系统：指标采集 + 对话反思 + Prompt 适配 + 用户画像
        memories_dir = os.path.join(self.workspace, "memories")
        self._metrics = MetricsCollector(memories_dir)
        self._profiler = UserProfiler(memories_dir)
        self._prompt_adapter = PromptAdapter(memories_dir, self._metrics)
        self._evolver = Evolver(
            llm=self.llm,
            memory=self.memory,
            metrics=self._metrics,
            profiler=self._profiler,
            min_tool_calls=config.evolution_reflect_min_tools,
            enabled=config.enable_evolution,
        )
        self._scheduler = EvolutionScheduler(
            metrics=self._metrics,
            adapter=self._prompt_adapter,
            profiler=self._profiler,
            base_dir=memories_dir,
            interval_hours=config.evolution_analysis_interval,
        )
        # 启动时检查是否需要执行定期深度分析
        if config.enable_evolution:
            self._scheduler.maybe_run()

        # 技能系统：基于 MD 文件的行为增强，存储在 workspace/skills/
        self.skills = SkillManager(os.path.join(self.workspace, "skills"))

        # 通用意图识别器（关键词预筛 + LLM 确认）
        self.intent_detector = IntentDetector(self.llm)

        system_content = build_system_prompt(
            self.workspace,
            tools_overview=build_tools_overview(),
            evolution_adaptations=self._prompt_adapter.get_adaptations() if config.enable_evolution else "",
        )
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]

        # ── 运行时状态 ──
        self._call_history: list[list[tuple[str, str]]] = []
        self._total_tokens: int = 0
        self._turn_tool_calls: list[dict] = []
        self._stop_requested: bool = False
        self._token_warned: bool = False

        # Plan-Execute-Reflect 状态
        self._plan_steps: list[str] = []
        self._current_step_idx: int = -1
        self._step_retries: int = 0

        # LATS 状态
        self._lats_fallback: list[str] = []
        self._lats_done_step: int = -1
        self._last_injected_step: int = -2

        # 动态范式升降级状态
        self._consecutive_successes: int = 0
        self._consecutive_failures: int = 0
        self._paradigm_level: int = 2  # 0=minimal, 1=standard, 2=full
        # Token 预算感知
        self._token_budget: int = config.context_token_threshold

        # Human-in-the-Loop 状态
        self._pending_confirmation: threading.Event | None = None
        self._confirmation_result: str | None = None
        self._confirmation_request_id: str = ""
        self._user_rejected_last: bool = False

        # ── 子模块 ──
        self.planner = Planner(self)
        self.lats = LatsStrategy(self)
        self.context = ContextManager(self)

    # ── 生命周期 ──────────────────────────────────────────────

    def __enter__(self) -> "Agent":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def stop(self) -> None:
        """请求停止当前运行。在下一个检查点安全终止。

        同时释放任何正在阻塞的 HITL 确认等待，使 Agent 线程能立即响应停止。
        """
        self._stop_requested = True
        # 释放 HITL 确认阻塞：让 _wait_for_confirmation 中的 event.wait() 立即返回
        event = self._pending_confirmation
        if event is not None:
            self._confirmation_result = "stop"
            event.set()

    def close(self) -> None:
        self.llm.close()

    # ── 事件发射 ──────────────────────────────────────────────

    def _emit(self, event: dict[str, Any]) -> None:
        """统一事件出口：有 on_event 回调时走回调，否则走终端打印。"""
        if self._on_event:
            self._on_event(event)
        else:
            self._print_event(event)

    def _print_event(self, event: dict[str, Any]) -> None:
        """CLI 模式下的事件打印（保持原有终端输出行为）。"""
        et = event["type"]
        if et == "reasoning_delta":
            if not getattr(self, "_streamed_any", False) or self._cur_kind != "reasoning":
                if getattr(self, "_streamed_any", False):
                    print()
                print("[reasoning] ", end="", flush=True)
                self._cur_kind = "reasoning"
            print(event["content"], end="", flush=True)
            self._streamed_any = True
        elif et == "content_delta":
            if not getattr(self, "_streamed_any", False) or self._cur_kind != "content":
                if getattr(self, "_streamed_any", False):
                    print()
                print("agent> ", end="", flush=True)
                self._cur_kind = "content"
            print(event["content"], end="", flush=True)
            self._streamed_any = True
        elif et == "stream_end":
            if getattr(self, "_streamed_any", False):
                print()
            self._streamed_any = False
        elif et == "reasoning":
            reasoning = event["content"]
            preview = reasoning if len(reasoning) <= 300 else reasoning[:300] + "..."
            print(f"[reasoning] {preview}")
        elif et == "usage":
            print(
                f"[usage] prompt={event['prompt_tokens']} "
                f"completion={event['completion_tokens']} "
                f"total={event['total_tokens']}"
            )
        elif et == "warning":
            print(f"[warn] {event['content']}")
        elif et == "tool_call":
            print(f"[tool] {event['name']}({event['args']})")
        elif et == "tool_result":
            preview = event.get("preview", event["result"])
            print(f"[result] {preview}")
        elif et == "separator":
            print("-" * 40)
        elif et == "context_compressed":
            before = event.get('before_messages', '?')
            after = event.get('after_messages', '?')
            saved = event.get('saved_tokens', 0)
            has_summary = '摘要' if event.get('has_summary') else '截断'
            print(f"[context] 已压缩: {before}→{after}条消息, 节省~{saved}tokens ({has_summary})")
        elif et == "token_warning":
            pct = event.get('usage_pct', 0)
            print(f"[token] ⚠ 上下文已使用约 {pct}%，可手动压缩")
        elif et == "plan_created":
            steps = event.get("steps", [])
            print(f"[plan] 生成执行计划 ({len(steps)} 步)")
            for i, s in enumerate(steps, 1):
                print(f"  STEP {i}: {s}")
        elif et == "reflection":
            result = event.get("result", "")
            detail = event.get("detail", "")
            preview = detail if len(detail) <= 100 else detail[:100] + "..."
            print(f"[reflect] {result} | {preview}")
        elif et == "lats_pick":
            pick = event.get("pick", 0)
            total = event.get("total", 0)
            chosen = event.get("chosen", "")
            print(f"[lats] 候选 {pick}/{total} → {chosen}")
        elif et == "done":
            pass  # 最终回复已由流式或上层处理
        elif et == "error":
            print(f"[error] {event['content']}")
        elif et == "file_ready":
            size = event.get("size", 0)
            size_str = (
                f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024
                else f"{size / 1024:.1f} KB" if size >= 1024
                else f"{size} B"
            )
            print(f"[file] {event.get('filename', '')} ({size_str}) -> {event.get('path', '')}")

    # ── 主循环 ────────────────────────────────────────────────

    def run(self, user_input: str) -> str:
        """运行单轮对话，返回模型最终文本回复。"""
        self._stop_requested = False
        self.messages.append({"role": "user", "content": user_input})
        self._turn_tool_calls = []

        # 注入已启用技能的指令（每轮对话注入一次，不侵入工具体系）
        self.context.inject_skills()

        # Episodic Memory：注入相关经验记忆
        self._inject_episodic_context(user_input)

        # Plan：复杂任务先拆解计划
        self.planner.create_plan(user_input)

        for iteration in range(self.config.max_iterations):
            if self._stop_requested:
                break
            self.context.maybe_compress()
            self.context.maybe_warn_token_usage()
            self.context.inject_guardrails(iteration)

            # 注入当前步骤上下文（让 LLM 知道当前应做什么）
            self.planner.inject_step_context()

            # LATS：生成候选方案并择优（受范式层级 + Token预算控制）
            if (
                self.config.enable_lats
                and self._plan_steps
                and self._current_step_idx >= 0
                and self._lats_done_step != self._current_step_idx
                and self._paradigm_level >= 2  # 仅 full 模式触发 LATS
                and self._get_lats_candidates() > 0  # Token 预算充足
            ):
                self.lats.branch()
                self._lats_done_step = self._current_step_idx

            on_delta = self._make_on_delta() if self.config.stream else None
            resp = self.llm.chat(
                self.messages,
                tools=self.registry.list_schemas(),
                stream=self.config.stream,
                on_delta=on_delta,
            )
            if self.config.stream:
                self._emit({"type": "stream_end"})

            choice = resp["choices"][0]
            msg = choice["message"]
            finish_reason = choice.get("finish_reason")

            # token 用量统计
            usage = resp.get("usage") or {}
            if usage:
                self._total_tokens = usage.get("total_tokens", self._total_tokens)
                self._emit({
                    "type": "usage",
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                })
            else:
                # fallback：API 未返回 usage 时用字符数粗估
                content_text = msg.get("content") or ""
                self._total_tokens += _estimate_tokens(content_text)

            # 非流式补发 reasoning；流式已在回调中输出
            if not self.config.stream:
                reasoning = msg.get("reasoning_content")
                if reasoning:
                    self._emit({"type": "reasoning", "content": reasoning})

            # finish_reason 异常处理
            if finish_reason == "length":
                self._emit({"type": "warning", "content": "输出因 max_tokens 被截断，考虑调大 MAX_TOKENS 或拆分任务"})
            elif finish_reason == "content_filter":
                self._emit({"type": "warning", "content": "内容被安全过滤拦截"})

            # 构造 assistant 消息（reasoning_content 不回填）
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": msg.get("content"),
            }
            if msg.get("tool_calls"):
                assistant_msg["tool_calls"] = msg["tool_calls"]
            self.messages.append(assistant_msg)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                reply = msg.get("content") or ""
                # 任务完成时，将剩余 plan 步骤全部标记为 DONE
                self._complete_remaining_steps()
                self._finish_turn(user_input, reply)
                return reply

            # 循环检测（滑动窗口）
            current_calls = [
                (tc.get("function", {}).get("name", ""),
                 tc.get("function", {}).get("arguments", ""))
                for tc in tool_calls
            ]
            if self.context.is_looping(current_calls):
                self._emit({"type": "warning", "content": "检测到工具调用可能陷入循环，主动停止"})
                # 循环检测中断：必须为所有 tool_call 补充 tool 消息
                self._fill_missing_tool_results(tool_calls)
                reply = "[检测到循环调用，已停止。请提供更多上下文或调整需求。]"
                self._finish_turn(user_input, reply)
                return reply
            self._call_history.append(current_calls)
            if len(self._call_history) > self.config.loop_window:
                self._call_history.pop(0)

            # ReWOO 并行工具编排：检测无依赖的多工具调用并行执行
            # 分类：需要确认的工具顺序执行，其他可并行
            hitl_calls = []  # 需要确认的调用
            parallel_calls = []  # 可并行执行的调用

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                tc_parsed = {"tc": tc, "name": name, "args": args}
                if self._needs_confirmation(name, args):
                    hitl_calls.append(tc_parsed)
                else:
                    parallel_calls.append(tc_parsed)

            # 先处理需要确认的工具（顺序）
            for item in hitl_calls:
                if self._stop_requested:
                    break
                tc, name, args = item["tc"], item["name"], item["args"]
                request_id = str(uuid.uuid4())[:8]
                reason = self._get_risk_reason(name, args)
                self._emit({
                    "type": "confirmation_request",
                    "tool_name": name,
                    "args": args,
                    "reason": reason,
                    "request_id": request_id,
                })
                decision = self._wait_for_confirmation(request_id, timeout=300)
                if decision == "stop" or self._stop_requested:
                    # 用户点击了停止，立即中断所有工具执行
                    result = f"[用户请求停止，跳过: {name}]"
                    self._emit({"type": "tool_result", "name": name, "result": result, "preview": result})
                    self.messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": name, "content": result})
                    break
                elif decision == "reject":
                    result = f"[用户拒绝执行: {name}，请采用替代方案]"
                    self._user_rejected_last = True
                    self._record_step_failure()
                    self._emit({"type": "tool_result", "name": name, "result": result, "preview": result})
                    self.messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": name, "content": result})
                    self.messages.append({"role": "system", "content": f"用户拒绝了 {name} 操作。请采用替代方案。"})
                    continue
                elif decision == "timeout":
                    result = f"[确认超时，跳过: {name}]"
                    self._emit({"type": "tool_result", "name": name, "result": result, "preview": result})
                    self.messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "name": name, "content": result})
                    continue
                # approve → 执行
                self._execute_tool(tc, name, args)

            # ReWOO: 无依赖工具并行执行
            if len(parallel_calls) > 1 and not self._stop_requested:
                self._execute_tools_parallel(parallel_calls)
            else:
                for item in parallel_calls:
                    if self._stop_requested:
                        break
                    self._execute_tool(item["tc"], item["name"], item["args"])

            # 停止检查：工具执行后（含 ReWOO 并行）已请求停止则直接退出循环
            if self._stop_requested:
                # 确保所有 tool_call 都有对应的 tool 消息
                self._fill_missing_tool_results(tool_calls)
                break

            self._emit({"type": "separator"})

            # Reflect：工具执行后自我评估（受范式层级控制）
            if self.config.enable_reflection and self._plan_steps:
                # 反思预判：工具全部成功时跳过 LLM 反思，直接推进下一步
                if self._should_skip_reflection():
                    self._advance_step()
                elif self._paradigm_level >= 1:  # standard/full 模式才执行反思
                    self.planner.reflect()
                    # 记录失败状态用于范式升级
                    if self._step_retries > 0:
                        self._record_step_failure()

        else:
            # for 循环正常结束（达到最大迭代次数）
            reply = "[已达到最大迭代次数，停止运行]"
            self._finish_turn(user_input, reply)
            return reply

        # for 循环被 break（手动停止）
        reply = "[已手动停止]"
        self._finish_turn(user_input, reply)
        return reply

    # ── 内部辅助 ──────────────────────────────────────────

    def _fill_missing_tool_results(self, tool_calls: list[dict]) -> None:
        """确保所有 tool_call_id 都有对应的 tool 消息，防止 API 报错。"""
        # 收集已响应的 tool_call_id
        responded_ids = set()
        for msg in reversed(self.messages):
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                responded_ids.add(msg["tool_call_id"])
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                break
        # 为缺失的 tool_call 补充占位响应
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            if tc_id and tc_id not in responded_ids:
                name = tc.get("function", {}).get("name", "unknown")
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": "[已跳过执行]",
                })

    def _execute_tool(self, tc: dict, name: str, args: dict) -> None:
        """执行单个工具调用，发射事件并记录结果。"""
        if self._stop_requested:
            # 即使停止也必须为每个 tool_call_id 提供响应
            self.messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": name,
                "content": "[用户请求停止，跳过执行]",
            })
            return
        self._emit({"type": "tool_call", "name": name, "args": args})

        # 指标采集：计时执行
        import time as _time
        _start = _time.perf_counter()
        result = self.registry.execute(name, args or {})
        _duration_ms = int((_time.perf_counter() - _start) * 1000)

        # 记录工具指标
        step_context = ""
        if self._plan_steps and 0 <= self._current_step_idx < len(self._plan_steps):
            step_context = self._plan_steps[self._current_step_idx]
        self._metrics.record_tool_call(
            tool_name=name,
            args=args,
            result=result,
            duration_ms=_duration_ms,
            context=step_context,
        )

        preview = result if len(result) <= 200 else result[:200] + "..."
        self._emit({"type": "tool_result", "name": name, "result": result, "preview": preview})
        self._turn_tool_calls.append({"name": name, "args": args, "result": result})
        self.messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "name": name,
            "content": result,
        })
        # Self-Verification：关键操作后自动验证
        self._self_verify(name, args, result)

    def _execute_tools_parallel(self, calls: list[dict]) -> None:
        """ReWOO 并行执行：多个无依赖工具并发调用。

        支持停止中断：在收集结果时检查 _stop_requested，
        取消未完成的 future 并立即返回。
        """
        self._emit({"type": "warning", "content": f"ReWOO: 并行执行 {len(calls)} 个工具调用"})
        results: dict[int, str] = {}
        stopped = False

        def _run(idx: int, item: dict) -> tuple[int, str]:
            if self._stop_requested:
                return idx, "[用户请求停止]"
            return idx, self.registry.execute(item["name"], item["args"] or {})

        # 先发射所有 tool_call 事件
        for item in calls:
            self._emit({"type": "tool_call", "name": item["name"], "args": item["args"]})

        with ThreadPoolExecutor(max_workers=min(4, len(calls))) as executor:
            futures = {executor.submit(_run, i, item): i for i, item in enumerate(calls)}
            for future in as_completed(futures):
                # 停止检查：收到停止信号后取消剩余 future 并退出
                if self._stop_requested and not stopped:
                    stopped = True
                    for f in futures:
                        f.cancel()
                try:
                    idx, result = future.result(timeout=0.1)
                    results[idx] = result
                except Exception:
                    # future 被取消或超时，跳过
                    pass

        # 按原始顺序处理结果
        for i, item in enumerate(calls):
            tc, name, args = item["tc"], item["name"], item["args"]
            result = results.get(i, "[用户请求停止]" if stopped else "Error: 并行执行失败")
            preview = result if len(result) <= 200 else result[:200] + "..."
            self._emit({"type": "tool_result", "name": name, "result": result, "preview": preview})
            self._turn_tool_calls.append({"name": name, "args": args, "result": result})
            self.messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": name,
                "content": result,
            })
            if not stopped:
                self._self_verify(name, args, result)

    # ── Self-Verification 自验证 ────────────────────────────

    # 需要验证的关键工具
    _VERIFY_TOOLS = {"write_file", "edit_file"}

    def _self_verify(self, name: str, args: dict, result: str) -> None:
        """关键操作后自动验证：确认文件写入/编辑实际生效。"""
        if name not in self._VERIFY_TOOLS:
            return
        if result.startswith("Error:"):
            return  # 已知失败，无需验证

        path = args.get("path", "")
        if not path:
            return

        try:
            if not os.path.exists(path):
                self._emit({"type": "warning", "content": f"Self-Verify 失败: {path} 不存在"})
                return
            size = os.path.getsize(path)
            if size == 0:
                self._emit({"type": "warning", "content": f"Self-Verify 警告: {path} 为空文件"})
            # 对 edit_file 验证编辑内容是否存在
            if name == "edit_file" and args.get("new_text"):
                with open(path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                snippet = args["new_text"][:50]
                if snippet not in content:
                    self._emit({"type": "warning", "content": f"Self-Verify 失败: 编辑内容未在文件中找到"})
        except OSError:
            pass  # 权限等问题，静默失败

    # ── 经验记忆引导 (Episodic Memory) ───────────────

    def _inject_episodic_context(self, user_input: str) -> None:
        """任务开始前查询相关经验记忆，注入作为参考。同时注入意图引导、工具建议和用户画像。"""
        try:
            parts = []

            # 意图识别和记忆检索并行执行，减少延迟
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=2) as pool:
                intent_future = pool.submit(self.intent_detector.detect, user_input)
                memory_future = pool.submit(self.memory.search, user_input.strip()[:50])

                # 收集意图结果
                try:
                    intents = intent_future.result(timeout=5.0)
                    for intent_name in intents:
                        guide = self.intent_detector.get_guide(intent_name)
                        if guide:
                            parts.append(guide)
                except Exception:
                    pass

                # 收集记忆结果
                try:
                    result = memory_future.result(timeout=3.0)
                    if result and "未找到" not in result and "为空" not in result:
                        parts.append(f"## 相关经验记忆\n\n{result[:500]}")
                except Exception:
                    pass

            # 自进化：工具使用建议
            if self.config.enable_evolution:
                tool_suggestions = self._metrics.get_tool_suggestions()
                if tool_suggestions:
                    parts.append(tool_suggestions)

                # 用户画像
                profile_summary = self._profiler.get_profile_summary()
                if profile_summary:
                    parts.append(profile_summary)

            if parts:
                context = "\n\n".join(parts)
                self.messages.append({"role": "system", "content": context})
        except Exception:
            pass  # 记忆系统不可用时静默跳过

    def _track_usage(self, resp: dict) -> None:
        """从 LLM 响应中提取 token 用量并更新累计值（供子模块调用）。"""
        self.context.track_usage(resp)

    def _should_skip_reflection(self) -> bool:
        """反思预判：工具全部成功且无警告时可跳过 LLM 反思。

        节省一次完整 LLM 调用（~500-2000 tokens）。
        """
        if self._current_step_idx < 0 or self._current_step_idx >= len(self._plan_steps):
            return False
        # 动态范式：minimal 模式下始终跳过反思
        if self._paradigm_level == 0:
            return True
        # 收集本轮工具结果
        recent_results = [tc.get("result", "") for tc in self._turn_tool_calls]
        if not recent_results:
            return False
        # 全部成功：无 Error 前缀、无警告词
        all_success = all(
            not r.startswith("Error:") and "error" not in r[:50].lower()
            for r in recent_results
        )
        return all_success

    def _advance_step(self) -> None:
        """快速推进到下一步（跳过 LLM 反思时使用）。"""
        self._current_step_idx += 1
        self._consecutive_successes += 1
        self._consecutive_failures = 0
        self._update_paradigm_level()
        self.planner.reset_flags()
        self._emit({"type": "reflection", "result": "DONE", "detail": "工具执行成功，自动推进"})

    def _complete_remaining_steps(self) -> None:
        """任务完成时，为所有未完成的 plan 步骤补发 DONE 事件。

        当 LLM 输出最终回复（无 tool_calls）时，意味着任务已完成，
        但前端需要 reflection 事件来更新每步的状态图标。
        """
        if not self._plan_steps or self._current_step_idx < 0:
            return
        while self._current_step_idx < len(self._plan_steps):
            self._emit({"type": "reflection", "result": "DONE", "detail": "任务完成，自动标记剩余步骤"})
            self._current_step_idx += 1

    # ── 动态范式升降级 ───────────────────────────────────

    def _update_paradigm_level(self) -> None:
        """根据连续成功/失败次数动态调整范式层级。

        Level 2 (full): ReAct + Plan + LATS + Reflection — 默认
        Level 1 (standard): ReAct + Plan + Reflection，跳过 LATS
        Level 0 (minimal): ReAct + Plan only，跳过 LATS和反思
        """
        old_level = self._paradigm_level

        # 降级逻辑：连续成功多次 → 减少开销
        if self._consecutive_successes >= 4 and self._paradigm_level > 0:
            self._paradigm_level = 0
        elif self._consecutive_successes >= 2 and self._paradigm_level > 1:
            self._paradigm_level = 1

        # 升级逻辑：出现失败 → 恢复完整范式
        if self._consecutive_failures >= 1 and self._paradigm_level < 2:
            self._paradigm_level = 2

        if old_level != self._paradigm_level:
            level_names = ["minimal", "standard", "full"]
            self._emit({
                "type": "paradigm_shift",
                "from": level_names[old_level],
                "to": level_names[self._paradigm_level],
            })

    def _record_step_failure(self) -> None:
        """记录步骤失败，触发范式升级。"""
        self._consecutive_failures += 1
        self._consecutive_successes = 0
        self._update_paradigm_level()

    # ── Token 预算感知 ────────────────────────────────────

    def _get_lats_candidates(self) -> int:
        """根据剩余 token 预算动态调整 LATS 候选数。

        - 预算充足(>70%): 保持配置值
        - 预算紧张(30-70%): 减少候选数
        - 预算不足(<30%): 完全跳过 LATS
        """
        if self._token_budget <= 0:
            return 0
        usage_ratio = self._total_tokens / self._token_budget
        if usage_ratio < 0.3:
            return self.config.lats_candidates  # 充足：保持配置值
        elif usage_ratio < 0.7:
            return max(2, self.config.lats_candidates - 1)  # 紧张：减1
        else:
            return 0  # 不足：跳过 LATS

    # ── Human-in-the-Loop ────────────────────────────────────

    def _needs_confirmation(self, name: str, args: dict) -> bool:
        """判断工具调用是否需要用户确认。"""
        mode = self.config.hitl_mode
        if mode == "none":
            return False
        if mode == "all":
            return True
        # risky 模式：检查工具名 + 动态检测
        if name in self.config.hitl_tools:
            return True
        # 动态检测：shell 命令中的高危操作
        if name == "run_shell":
            cmd = str(args.get("command", ""))
            dangerous = ["rm ", "sudo ", "chmod", "curl ", "wget ", ">", "|", "&&"]
            return any(d in cmd for d in dangerous)
        return False

    def _get_risk_reason(self, name: str, args: dict) -> str:
        """生成人类可读的风险说明。"""
        if name == "run_shell":
            return f"即将执行 Shell 命令: {str(args.get('command', ''))[:120]}"
        elif name == "write_file":
            return f"即将覆盖写入文件: {args.get('path', '')}"
        elif name == "edit_file":
            return f"即将修改文件: {args.get('path', '')}"
        return f"即将执行工具: {name}"

    def _wait_for_confirmation(self, request_id: str, timeout: int = 300) -> str:
        """阻塞等待用户确认/拒绝，支持超时。线程安全。"""
        event = threading.Event()
        self._pending_confirmation = event
        self._confirmation_result = None
        self._confirmation_request_id = request_id

        got_response = event.wait(timeout=timeout)
        self._pending_confirmation = None
        self._confirmation_request_id = ""
        if not got_response:
            return "timeout"
        return self._confirmation_result or "reject"

    def handle_confirmation(self, request_id: str, decision: str) -> None:
        """接收用户确认/拒绝决策（由 WebSocket 层调用）。线程安全。"""
        if (self._confirmation_request_id == request_id
                and self._pending_confirmation is not None):
            self._confirmation_result = decision
            self._pending_confirmation.set()

    def _finish_turn(self, user_input: str, reply: str) -> None:
        """保存对话历史到记忆系统并发射 done 事件。触发自进化反思。"""
        self.memory.save_turn(
            user_input=user_input,
            reply=reply,
            tool_calls=self._turn_tool_calls or None,
        )
        self._emit({"type": "done", "content": reply})

        # 自进化：对话后反思 + 用户画像更新 + 对话指标记录
        if self.config.enable_evolution:
            # 用户画像轻量更新（无 LLM 调用）
            self._profiler.update_from_conversation(
                user_input, reply, self._turn_tool_calls or []
            )
            # 异步反思（后台 LLM 调用）
            self._evolver.post_conversation_reflect(
                user_input=user_input,
                tool_calls=self._turn_tool_calls or [],
                reply=reply,
                plan_steps=self._plan_steps or None,
            )
            # 对话级指标记录
            tool_failures = sum(
                1 for tc in (self._turn_tool_calls or [])
                if tc.get("result", "").startswith("Error:")
            )
            level_names = ["minimal", "standard", "full"]
            self._metrics.record_conversation(
                user_input_len=len(user_input),
                total_turns=len(self._call_history),
                plan_steps=len(self._plan_steps),
                success=not reply.startswith("["),
                paradigm_used=level_names[self._paradigm_level],
                total_tokens=self._total_tokens,
                duration_s=0,  # TODO: 跟踪对话总耗时
                tool_calls_count=len(self._turn_tool_calls or []),
                tool_failures=tool_failures,
            )

    def compress_context(self) -> dict:
        """手动压缩上下文（由 WebSocket 层调用）。"""
        return self.context.compress_context(force=False)

    def reset(self) -> None:
        """清空对话历史，仅保留 system prompt。"""
        self.messages = [self.messages[0]]
        self._call_history = []
        self._total_tokens = 0
        self._plan_steps = []
        self._current_step_idx = -1
        self._lats_fallback = []
        self._token_warned = False
        self.planner.reset_flags()

    def _make_on_delta(self):
        """返回流式回调，将 delta 转为事件发射。"""
        def cb(kind: str, text: str) -> None:
            if kind == "reasoning":
                self._emit({"type": "reasoning_delta", "content": text})
            else:
                self._emit({"type": "content_delta", "content": text})

        return cb
