"""Adapter for the Anthropic Messages API (not the default provider; see DECISIONS.md D3)."""

from collections.abc import AsyncIterator
from typing import Any, Literal

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import Message

from marketmind.llm.pricing import cost_usd
from marketmind.llm.types import (
    LLMError,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
    StreamDone,
    StreamEvent,
    TextDelta,
)

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class AnthropicProvider:
    def __init__(self, client: AsyncAnthropic, *, effort: Effort = "low") -> None:
        self.name = "anthropic"
        self._client = client
        self._effort = effort

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            message = await self._client.messages.create(**self._params(request))
        except anthropic.APIError as exc:
            raise self._error(exc) from exc
        return self._parse(message, request.model)

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        try:
            async with self._client.messages.stream(**self._params(request)) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text=text)
                final = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise self._error(exc) from exc
        yield StreamDone(response=self._parse(final, request.model))

    def _params(self, request: LLMRequest) -> dict[str, Any]:
        # Current Claude models removed sampling params, so `request.temperature` is not sent.
        output_config: dict[str, Any] = {"effort": self._effort}
        if request.response_schema is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": _strict(request.response_schema),
            }
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": _wire_messages(request.messages),
            "output_config": output_config,
        }
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        if system:
            params["system"] = system
        if request.tools:
            params["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in request.tools
            ]
        return params

    def _parse(self, message: Message, model: str) -> LLMResponse:
        text = "".join(block.text for block in message.content if block.type == "text")
        tool_calls = [
            LLMToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            for block in message.content
            if block.type == "tool_use"
        ]
        usage = message.usage
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=LLMUsage(
                tokens_in=usage.input_tokens,
                tokens_out=usage.output_tokens,
                usd=cost_usd(model, usage.input_tokens, usage.output_tokens),
            ),
            model=message.model,
            finish_reason=message.stop_reason or "end_turn",
            # Thinking blocks must go back unchanged on the next turn.
            provider_raw={
                "content": [b.model_dump(mode="json", exclude_none=True) for b in message.content]
            },
        )

    def _error(self, exc: anthropic.APIError) -> LLMError:
        if isinstance(exc, anthropic.APIConnectionError):  # includes APITimeoutError
            retryable = True
        elif isinstance(exc, anthropic.APIStatusError):
            retryable = exc.status_code == 429 or exc.status_code >= 500
        else:
            retryable = False
        return LLMError(f"{type(exc).__name__}: {exc}", retryable=retryable, provider=self.name)


def _wire_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    """Map neutral messages to Anthropic turns: system goes top-level, and consecutive
    user-side entries (tool results, user text) merge into one user turn."""
    wire: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            continue
        if m.role == "assistant":
            if m.provider_raw is not None:
                content: Any = m.provider_raw["content"]
            else:
                content = [{"type": "text", "text": m.content}] if m.content else []
                content += [
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in m.tool_calls
                ]
            wire.append({"role": "assistant", "content": content})
            continue
        block: dict[str, Any] = (
            {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
            if m.role == "tool"
            else {"type": "text", "text": m.content}
        )
        if wire and wire[-1]["role"] == "user":
            previous = wire[-1]
            if isinstance(previous["content"], str):
                previous["content"] = [{"type": "text", "text": previous["content"]}]
            previous["content"].append(block)
        elif m.role == "tool":
            wire.append({"role": "user", "content": [block]})
        else:
            wire.append({"role": "user", "content": m.content})
    return wire


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Structured outputs need `additionalProperties: false` on every object schema."""
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            out[key] = _strict(value)
        elif isinstance(value, list):
            out[key] = [_strict(v) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out
