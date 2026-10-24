import io
import json
from collections.abc import AsyncIterator

import pytest

from marketmind.core.logging import configure_logging
from marketmind.llm.fake import FakeLLMProvider
from marketmind.llm.fallback import FallbackProvider
from marketmind.llm.types import (
    LLMError,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    StreamDone,
    StreamEvent,
    TextDelta,
)

REQ = LLMRequest(
    node="router",
    model="deepseek/deepseek-v4.1-flash-1017",
    messages=[LLMMessage(role="user", content="q")],
)


class Failing:
    name = "primary"

    def __init__(self, *, retryable: bool, after_deltas: int = 0) -> None:
        self.retryable = retryable
        self.after_deltas = after_deltas

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise LLMError("boom", retryable=self.retryable, provider=self.name)

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        for _ in range(self.after_deltas):
            yield TextDelta(text="partial ")
        raise LLMError("boom", retryable=self.retryable, provider=self.name)


def _fallback() -> FakeLLMProvider:
    fake = FakeLLMProvider()
    fake.script("router", "from fallback")
    return fake


async def test_retryable_failure_falls_back_with_the_fallback_model() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    backup = _fallback()
    provider = FallbackProvider(
        Failing(retryable=True), backup, fallback_model="z-ai/glm-5.3-flash"
    )

    response = await provider.complete(REQ)

    assert response.text == "from fallback"
    assert backup.requests[0].model == "z-ai/glm-5.3-flash"
    [line] = [json.loads(x) for x in stream.getvalue().splitlines()]
    assert line["event"] == "llm_fallback"
    assert line["node"] == "router"
    assert line["fallback_model"] == "z-ai/glm-5.3-flash"
    configure_logging("INFO")


async def test_non_retryable_failure_is_not_retried_elsewhere() -> None:
    backup = _fallback()
    provider = FallbackProvider(Failing(retryable=False), backup, fallback_model="z")
    with pytest.raises(LLMError):
        await provider.complete(REQ)
    assert backup.requests == []


async def test_stream_falls_back_only_before_the_first_delta() -> None:
    provider = FallbackProvider(Failing(retryable=True), _fallback(), fallback_model="z")
    events = [e async for e in provider.stream(REQ)]
    assert isinstance(events[-1], StreamDone)
    assert events[-1].response.text == "from fallback"

    started = FallbackProvider(Failing(retryable=True, after_deltas=1), _fallback(), "z")
    with pytest.raises(LLMError):
        _ = [e async for e in started.stream(REQ)]
