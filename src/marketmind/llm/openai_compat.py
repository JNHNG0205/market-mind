"""Adapter for any OpenAI-compatible chat API (OpenRouter by default; see DECISIONS.md D3-D6)."""

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

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


class OpenAICompatProvider:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        name: str = "openrouter",
        extra_body: Mapping[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._client = client
        # OpenRouter routing (e.g. pinning the DeepSeek host) rides in the request body.
        self._extra_body = dict(extra_body or {})

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            completion = await self._client.chat.completions.create(**self._params(request))
        except openai.APIError as exc:
            raise self._error(exc) from exc
        return self._parse(completion, request.model)

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        text: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish = "stop"
        usage: CompletionUsage | None = None
        try:
            chunks = await self._client.chat.completions.create(
                **self._params(request), stream=True, stream_options={"include_usage": True}
            )
            async for chunk in chunks:
                usage = chunk.usage or usage
                for choice in chunk.choices:
                    finish = choice.finish_reason or finish
                    if choice.delta.content:
                        text.append(choice.delta.content)
                        yield TextDelta(text=choice.delta.content)
                    for call in choice.delta.tool_calls or []:
                        acc = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                        acc["id"] = call.id or acc["id"]
                        if call.function is not None:
                            acc["name"] += call.function.name or ""
                            acc["arguments"] += call.function.arguments or ""
        except openai.APIError as exc:
            raise self._error(exc) from exc

        tool_calls = [
            LLMToolCall(id=c["id"], name=c["name"], arguments=self._arguments(c["arguments"]))
            for _, c in sorted(calls.items())
        ]
        raw: dict[str, Any] = {"role": "assistant", "content": "".join(text)}
        if tool_calls:
            raw["tool_calls"] = [_wire_tool_call(c) for c in tool_calls]
        yield StreamDone(
            response=LLMResponse(
                text="".join(text),
                tool_calls=tool_calls,
                usage=self._usage(usage, request.model),
                model=request.model,
                finish_reason=finish,
                provider_raw=raw,
            )
        )

    def _params(self, request: LLMRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model,
            "messages": [_wire_message(m) for m in request.messages],
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]
        if request.response_schema is not None:
            # JSON mode only: the DeepSeek host doesn't enforce json_schema (D6).
            # `complete_json` puts the schema in the prompt and validates the reply.
            params["response_format"] = {"type": "json_object"}
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if self._extra_body:
            params["extra_body"] = self._extra_body
        return params

    def _parse(self, completion: ChatCompletion, model: str) -> LLMResponse:
        if not completion.choices:
            raise LLMError("provider returned no choices", retryable=True, provider=self.name)
        choice = completion.choices[0]
        message: ChatCompletionMessage = choice.message
        tool_calls = [
            LLMToolCall(
                id=call.id,
                name=call.function.name,
                arguments=self._arguments(call.function.arguments),
            )
            for call in message.tool_calls or []
            if call.type == "function"
        ]
        return LLMResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            usage=self._usage(completion.usage, model),
            model=completion.model or model,
            finish_reason=choice.finish_reason or "stop",
            provider_raw=message.model_dump(mode="json", exclude_none=True),
        )

    def _arguments(self, raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"model sent unparseable tool arguments: {exc}", retryable=True, provider=self.name
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMError(
                "model sent tool arguments that are not an object",
                retryable=True,
                provider=self.name,
            )
        return parsed

    @staticmethod
    def _usage(usage: CompletionUsage | None, model: str) -> LLMUsage:
        if usage is None:
            return LLMUsage()
        reported = (usage.model_extra or {}).get("cost")
        usd = (
            float(reported)
            if isinstance(reported, int | float)
            else cost_usd(model, usage.prompt_tokens, usage.completion_tokens)
        )
        return LLMUsage(tokens_in=usage.prompt_tokens, tokens_out=usage.completion_tokens, usd=usd)

    def _error(self, exc: openai.APIError) -> LLMError:
        if isinstance(exc, openai.APIConnectionError):  # includes APITimeoutError
            retryable = True
        elif isinstance(exc, openai.APIStatusError):
            # OpenRouter answers 404 "No endpoints found" when routing leaves no host:
            # a provider-side failure the fallback model can work around (D38).
            no_endpoints = exc.status_code == 404 and "no endpoints found" in str(exc).lower()
            retryable = exc.status_code == 429 or exc.status_code >= 500 or no_endpoints
        else:
            retryable = False
        return LLMError(f"{type(exc).__name__}: {exc}", retryable=retryable, provider=self.name)


def _wire_tool_call(call: LLMToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
    }


def _wire_message(message: LLMMessage) -> dict[str, Any]:
    if message.role == "assistant":
        if message.provider_raw is not None:
            return message.provider_raw
        wire: dict[str, Any] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            wire["tool_calls"] = [_wire_tool_call(c) for c in message.tool_calls]
        return wire
    if message.role == "tool":
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
    return {"role": message.role, "content": message.content}
