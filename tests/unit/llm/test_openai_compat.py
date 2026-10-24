import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from marketmind.llm.openai_compat import OpenAICompatProvider
from marketmind.llm.types import (
    LLMError,
    LLMMessage,
    LLMRequest,
    LLMToolCall,
    LLMToolSpec,
    StreamDone,
    TextDelta,
)

MODEL = "deepseek/deepseek-v4.1-flash-1017"
PIN = {"provider": {"order": ["DeepSeek"], "allow_fallbacks": False}}
Handler = Callable[[httpx2.Request], httpx2.Response]


class Capture:
    def __init__(self, *responses: httpx2.Response) -> None:
        self.responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        return self.responses.pop(0)


def _provider(handler: Handler, **kwargs: Any) -> OpenAICompatProvider:
    client = AsyncOpenAI(
        api_key="test",
        base_url="https://openrouter.test/api/v1",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return OpenAICompatProvider(client, **kwargs)


def _completion(message: dict[str, Any], **usage: Any) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "gen-1",
            "object": "chat.completion",
            "created": 1761300000,
            "model": MODEL,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, **usage},
        },
    )


def _request(**kwargs: Any) -> LLMRequest:
    messages = [LLMMessage(role="system", content="sys"), LLMMessage(role="user", content="hi")]
    return LLMRequest(node="router", model=MODEL, messages=messages, **kwargs)


async def test_complete_returns_text_and_priced_usage_and_pins_the_provider() -> None:
    capture = Capture(_completion({"role": "assistant", "content": "hello"}))
    response = await _provider(capture, extra_body=PIN).complete(_request(temperature=0))
    assert response.text == "hello"
    assert response.finish_reason == "stop"
    assert response.usage.tokens_in == 100
    assert response.usage.tokens_out == 20
    assert response.usage.usd == pytest.approx((100 * 0.21 + 20 * 0.84) / 1_000_000)
    [body] = capture.bodies
    assert body["provider"] == PIN["provider"]
    assert body["model"] == MODEL
    assert body["temperature"] == 0
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    assert "response_format" not in body
    assert "tools" not in body


async def test_cost_reported_by_openrouter_wins_over_the_price_table() -> None:
    capture = Capture(_completion({"role": "assistant", "content": "x"}, cost=0.00042))
    response = await _provider(capture).complete(_request())
    assert response.usage.usd == pytest.approx(0.00042)


async def test_response_schema_turns_on_json_mode() -> None:
    capture = Capture(_completion({"role": "assistant", "content": "{}"}))
    await _provider(capture).complete(_request(response_schema={"type": "object"}))
    assert capture.bodies[0]["response_format"] == {"type": "json_object"}


async def test_tool_calls_parse_and_the_raw_assistant_turn_is_echoed_back() -> None:
    assistant = {
        "role": "assistant",
        "content": "",
        "reasoning": "need the price first",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_price", "arguments": '{"symbol": "BTCUSDT"}'},
            }
        ],
    }
    capture = Capture(_completion(assistant), _completion({"role": "assistant", "content": "done"}))
    provider = _provider(capture)
    tool = LLMToolSpec(name="get_price", description="Last price", input_schema={"type": "object"})

    first = await provider.complete(_request(tools=[tool]))
    assert first.tool_calls == [
        LLMToolCall(id="call_1", name="get_price", arguments={"symbol": "BTCUSDT"})
    ]
    assert capture.bodies[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_price",
                "description": "Last price",
                "parameters": {"type": "object"},
            },
        }
    ]

    history = [
        LLMMessage(role="user", content="btc?"),
        first.as_message(),
        LLMMessage(role="tool", tool_call_id="call_1", content='{"price": 1}'),
    ]
    await provider.complete(LLMRequest(node="planner", model=MODEL, messages=history))
    sent = capture.bodies[1]["messages"]
    assert sent[1]["reasoning"] == "need the price first"
    assert sent[1]["tool_calls"][0]["id"] == "call_1"
    assert sent[2] == {"role": "tool", "tool_call_id": "call_1", "content": '{"price": 1}'}


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (500, True), (503, True), (400, False), (401, False)]
)
async def test_http_errors_become_llm_errors(status: int, retryable: bool) -> None:
    capture = Capture(httpx2.Response(status, json={"error": {"message": "nope"}}))
    with pytest.raises(LLMError) as info:
        await _provider(capture).complete(_request())
    assert info.value.retryable is retryable
    assert info.value.provider == "openrouter"


async def test_empty_choices_is_a_retryable_error() -> None:
    body = {"id": "gen-1", "object": "chat.completion", "created": 1, "model": MODEL, "choices": []}
    with pytest.raises(LLMError) as info:
        await _provider(Capture(httpx2.Response(200, json=body))).complete(_request())
    assert info.value.retryable is True


async def test_unparseable_tool_arguments_are_a_retryable_error() -> None:
    assistant = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "f", "arguments": "{oops"}}
        ],
    }
    with pytest.raises(LLMError, match="tool arguments"):
        await _provider(Capture(_completion(assistant))).complete(_request())


def _sse(*chunks: dict[str, Any]) -> httpx2.Response:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx2.Response(200, text=body, headers={"content-type": "text/event-stream"})


def _chunk(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
    return {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


async def test_stream_yields_deltas_then_one_done_with_usage() -> None:
    usage_chunk = {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": MODEL,
        "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    }
    capture = Capture(
        _sse(
            _chunk({"role": "assistant", "content": "Hel"}),
            _chunk({"content": "lo"}),
            _chunk({}, finish="stop"),
            usage_chunk,
        )
    )
    events = [e async for e in _provider(capture).stream(_request())]
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hel", "lo"]
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert done.response.text == "Hello"
    assert done.response.finish_reason == "stop"
    assert done.response.usage.tokens_in == 10
    assert capture.bodies[0]["stream_options"] == {"include_usage": True}


async def test_stream_errors_become_llm_errors() -> None:
    capture = Capture(httpx2.Response(503, json={"error": {"message": "overloaded"}}))
    with pytest.raises(LLMError) as info:
        _ = [e async for e in _provider(capture).stream(_request())]
    assert info.value.retryable is True


async def test_no_endpoints_404_is_retryable_so_the_fallback_can_run() -> None:
    error = {
        "error": {"message": "No endpoints found for deepseek/x. Every candidate...", "code": 404}
    }
    capture = Capture(httpx2.Response(404, json=error))
    with pytest.raises(LLMError) as info:
        await _provider(capture).complete(_request())
    assert info.value.retryable is True


async def test_other_404s_stay_non_retryable() -> None:
    capture = Capture(httpx2.Response(404, json={"error": {"message": "model not found"}}))
    with pytest.raises(LLMError) as info:
        await _provider(capture).complete(_request())
    assert info.value.retryable is False
