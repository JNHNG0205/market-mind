"""Opt-in smoke tests against the real configured provider: `LIVE_TESTS=1 uv run pytest -m live`."""

import pytest
from pydantic import BaseModel

from marketmind.core.config import Settings
from marketmind.llm.factory import build_llm
from marketmind.llm.structured import complete_json
from marketmind.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMToolSpec,
    StreamDone,
    TextDelta,
)

pytestmark = pytest.mark.live

PRICE_TOOL = LLMToolSpec(
    name="get_price",
    description="Last traded price for an exchange pair such as BTCUSDT.",
    input_schema={
        "type": "object",
        "properties": {"symbol": {"type": "string"}},
        "required": ["symbol"],
    },
)


class Sum(BaseModel):
    answer: int


async def test_structured_json() -> None:
    settings = Settings()
    llm = build_llm(settings)
    request = LLMRequest(
        node="router",
        model=settings.llm_model_router,
        messages=[LLMMessage(role="user", content="What is 2 + 3?")],
        temperature=0,
        max_tokens=256,
    )
    result = await complete_json(llm, request, Sum)
    assert result.value.answer == 5
    assert result.usage.tokens_in > 0
    assert result.usage.usd > 0


async def test_tool_call_then_answer_with_echoed_history() -> None:
    settings = Settings()
    llm = build_llm(settings)
    messages = [
        LLMMessage(role="system", content="Use tools for market data. Answer in one sentence."),
        LLMMessage(role="user", content="What is bitcoin trading at?"),
    ]
    first = await llm.complete(
        LLMRequest(
            node="planner",
            model=settings.llm_model_planner,
            messages=messages,
            tools=[PRICE_TOOL],
            max_tokens=512,
        )
    )
    assert [c.name for c in first.tool_calls] == ["get_price"]
    call = first.tool_calls[0]
    assert "BTC" in call.arguments["symbol"].upper()

    history = [
        *messages,
        first.as_message(),
        LLMMessage(role="tool", tool_call_id=call.id, content='{"symbol": "BTCUSDT", "price": 1}'),
    ]
    second = await llm.complete(
        LLMRequest(
            node="planner",
            model=settings.llm_model_planner,
            messages=history,
            tools=[PRICE_TOOL],
            max_tokens=512,
        )
    )
    assert second.text.strip()


async def test_stream() -> None:
    settings = Settings()
    llm = build_llm(settings)
    request = LLMRequest(
        node="composer",
        model=settings.llm_model_composer,
        messages=[LLMMessage(role="user", content="Say hello in exactly three words.")],
        max_tokens=128,
    )
    events = [e async for e in llm.stream(request)]
    deltas = [e.text for e in events if isinstance(e, TextDelta)]
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert "".join(deltas) == done.response.text
    assert done.response.text.strip()
