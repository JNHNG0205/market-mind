from typing import Literal

import pytest
from pydantic import BaseModel

from marketmind.llm.fake import FakeLLMProvider
from marketmind.llm.structured import complete_json
from marketmind.llm.types import LLMMessage, LLMOutputError, LLMRequest, LLMUsage


class Route(BaseModel):
    intent: Literal["price_lookup", "off_topic"]
    confidence: float


def _req() -> LLMRequest:
    return LLMRequest(
        node="router",
        model="m",
        messages=[
            LLMMessage(role="system", content="You route queries."),
            LLMMessage(role="user", content="btc price?"),
        ],
    )


def _usage() -> LLMUsage:
    return LLMUsage(tokens_in=10, tokens_out=5, usd=0.001)


async def test_valid_json_parses_on_the_first_attempt() -> None:
    fake = FakeLLMProvider()
    fake.script("router", '{"intent": "price_lookup", "confidence": 0.9}', usage=_usage())
    result = await complete_json(fake, _req(), Route)
    assert result.value == Route(intent="price_lookup", confidence=0.9)
    assert result.attempts == 1
    assert result.usage == _usage()

    sent = fake.requests[0]
    assert sent.response_schema == Route.model_json_schema()
    assert sent.messages[0].role == "system"
    assert "You route queries." in sent.messages[0].content
    assert '"intent"' in sent.messages[0].content  # schema embedded for JSON-mode providers


async def test_code_fenced_json_is_accepted() -> None:
    fake = FakeLLMProvider()
    fake.script("router", '```json\n{"intent": "off_topic", "confidence": 1}\n```')
    result = await complete_json(fake, _req(), Route)
    assert result.value.intent == "off_topic"


async def test_invalid_reply_is_retried_once_with_the_error() -> None:
    fake = FakeLLMProvider()
    fake.script("router", '{"intent": "buy_now", "confidence": 0.9}', usage=_usage())
    fake.script("router", '{"intent": "price_lookup", "confidence": 0.8}', usage=_usage())
    result = await complete_json(fake, _req(), Route)
    assert result.value.intent == "price_lookup"
    assert result.attempts == 2
    assert result.usage.tokens_in == 20
    retry = fake.requests[1].messages
    assert retry[-2].role == "assistant"
    assert retry[-1].role == "user"
    assert "intent" in retry[-1].content  # the validation error is fed back


async def test_two_invalid_replies_raise_llm_output_error() -> None:
    fake = FakeLLMProvider()
    fake.script("router", "not json")
    fake.script("router", "still not json")
    with pytest.raises(LLMOutputError) as info:
        await complete_json(fake, _req(), Route)
    assert info.value.attempts == 2
    fake.assert_exhausted()
