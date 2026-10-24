import json
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic

from marketmind.llm.anthropic_provider import AnthropicProvider
from marketmind.llm.types import LLMError, LLMMessage, LLMRequest, LLMToolCall, LLMToolSpec

MODEL = "claude-haiku-5-5"


class Capture:
    def __init__(self, *responses: httpx2.Response) -> None:
        self.responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        return self.responses.pop(0)


def _provider(capture: Capture) -> AnthropicProvider:
    client = AsyncAnthropic(
        api_key="test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(capture)),
    )
    return AnthropicProvider(client, effort="low")


def _message(content: list[dict[str, Any]], stop: str = "end_turn") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": MODEL,
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 10},
        },
    )


TOOL_TURN: list[dict[str, Any]] = [
    {"type": "thinking", "thinking": "", "signature": "sig-abc"},
    {"type": "text", "text": "Checking."},
    {"type": "tool_use", "id": "toolu_1", "name": "get_price", "input": {"symbol": "BTCUSDT"}},
]


def _request(messages: list[LLMMessage] | None = None, **kwargs: Any) -> LLMRequest:
    messages = messages or [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="btc?"),
    ]
    return LLMRequest(node="planner", model=MODEL, messages=messages, **kwargs)


async def test_complete_parses_text_and_tool_use_and_sends_no_sampling_params() -> None:
    capture = Capture(_message(TOOL_TURN, stop="tool_use"))
    tool = LLMToolSpec(name="get_price", description="Last price", input_schema={"type": "object"})
    response = await _provider(capture).complete(_request(tools=[tool], temperature=0))

    assert response.text == "Checking."
    assert response.tool_calls == [
        LLMToolCall(id="toolu_1", name="get_price", arguments={"symbol": "BTCUSDT"})
    ]
    assert response.finish_reason == "tool_use"
    assert response.usage.usd == pytest.approx((50 * 0.10 + 10 * 0.50) / 1_000_000)
    [body] = capture.bodies
    assert body["system"] == "sys"
    assert body["messages"] == [{"role": "user", "content": "btc?"}]
    assert body["tools"] == [
        {"name": "get_price", "description": "Last price", "input_schema": {"type": "object"}}
    ]
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body


async def test_history_echoes_thinking_blocks_and_batches_tool_results() -> None:
    capture = Capture(
        _message(TOOL_TURN, stop="tool_use"), _message([{"type": "text", "text": "ok"}])
    )
    provider = _provider(capture)
    first = await provider.complete(_request())

    history = [
        LLMMessage(role="system", content="sys"),
        LLMMessage(role="user", content="btc?"),
        first.as_message(),
        LLMMessage(role="tool", tool_call_id="toolu_1", content='{"price": 1}'),
        LLMMessage(role="tool", tool_call_id="toolu_2", content='{"price": 2}'),
    ]
    await provider.complete(_request(history))
    sent = capture.bodies[1]["messages"]
    assert sent[1] == {"role": "assistant", "content": TOOL_TURN}
    assert sent[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"price": 1}'},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": '{"price": 2}'},
        ],
    }


async def test_response_schema_uses_native_structured_output() -> None:
    capture = Capture(_message([{"type": "text", "text": "{}"}]))
    schema = {"type": "object", "properties": {"a": {"type": "object", "properties": {}}}}
    await _provider(capture).complete(_request(response_schema=schema))
    fmt = capture.bodies[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    assert fmt["schema"]["properties"]["a"]["additionalProperties"] is False


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (529, True), (400, False)])
async def test_http_errors_become_llm_errors(status: int, retryable: bool) -> None:
    error = {"type": "error", "error": {"type": "x", "message": "nope"}}
    capture = Capture(httpx2.Response(status, json=error))
    with pytest.raises(LLMError) as info:
        await _provider(capture).complete(_request())
    assert info.value.retryable is retryable
    assert info.value.provider == "anthropic"
