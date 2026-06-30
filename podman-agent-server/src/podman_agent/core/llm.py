"""LLM 客户端：基于 OpenAI 官方 SDK 调用 DeepSeek 兼容接口。

为保持上层 Agent 主循环不受协议细节影响，本模块对外仍返回 dict 形态
（与 OpenAI 非流式响应结构一致）；流式模式下边收边触发 on_delta 回调，
最终聚合为同一形态返回。

思考模式（enable_thinking）默认关闭，通过 extra_body 透传，避免 reasoner 类
模型不支持时报错。
"""
from __future__ import annotations

from typing import Any, Callable

from openai import OpenAI

OnDelta = Callable[[str, str], None]
"""on_delta(kind, text)：kind ∈ {"content", "reasoning"}, text 为该次 delta 文本。"""


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        top_p: float | None = None,
        max_tokens: int | None = None,
        enable_thinking: bool = False,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        response_format: dict[str, Any] | None,
        stop: str | list[str] | None,
        frequency_penalty: float | None,
        presence_penalty: float | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if stop is not None:
            kwargs["stop"] = stop
        if frequency_penalty is not None:
            kwargs["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            kwargs["presence_penalty"] = presence_penalty
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        # 思考模式开关：DeepSeek v4 识别 extra_body.thinking.type 字段。
        # 默认 disabled；启用时不传该字段，遵从服务端默认。
        if not self.enable_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return kwargs

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = False,
        on_delta: OnDelta | None = None,
        response_format: dict[str, Any] | None = None,
        stop: str | list[str] | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> dict[str, Any]:
        kwargs = self._build_kwargs(
            messages, tools, response_format, stop, frequency_penalty, presence_penalty
        )

        if not stream:
            resp = self._client.chat.completions.create(**kwargs)
            return resp.model_dump()

        # 流式：开启 SSE 并请求末尾返回 usage
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        return self._chat_stream(kwargs, on_delta)

    def _chat_stream(
        self,
        kwargs: dict[str, Any],
        on_delta: OnDelta | None,
    ) -> dict[str, Any]:
        accumulated_content: list[str] = []
        accumulated_reasoning: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] | None = None

        stream = self._client.chat.completions.create(**kwargs)
        for chunk in stream:
            chunk_dict = chunk.model_dump()

            # usage 通常在最后一个 chunk 出现，且 choices 可能为空
            if chunk_dict.get("usage"):
                usage = chunk_dict["usage"]

            choices = chunk_dict.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}

            content_piece = delta.get("content")
            if content_piece:
                accumulated_content.append(content_piece)
                if on_delta:
                    on_delta("content", content_piece)

            reasoning_piece = delta.get("reasoning_content")
            if reasoning_piece:
                accumulated_reasoning.append(reasoning_piece)
                if on_delta:
                    on_delta("reasoning", reasoning_piece)

            # tool_calls 按 index 累积合并
            for tc_delta in delta.get("tool_calls") or []:
                idx = tc_delta.get("index", 0)
                tc = tool_calls_by_index.setdefault(
                    idx,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if tc_delta.get("id"):
                    tc["id"] = tc_delta["id"]
                if tc_delta.get("type"):
                    tc["type"] = tc_delta["type"]
                fn = tc_delta.get("function") or {}
                if fn.get("name"):
                    tc["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    tc["function"]["arguments"] += fn["arguments"]

            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

        # 装配为与非流式一致的响应结构
        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(accumulated_content) or None,
        }
        if accumulated_reasoning:
            message["reasoning_content"] = "".join(accumulated_reasoning)
        if tool_calls_by_index:
            message["tool_calls"] = [
                tool_calls_by_index[i] for i in sorted(tool_calls_by_index)
            ]

        return {
            "choices": [{"message": message, "finish_reason": finish_reason}],
            "usage": usage,
        }

    def close(self) -> None:
        self._client.close()