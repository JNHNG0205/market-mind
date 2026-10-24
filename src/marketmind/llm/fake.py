"""Scripted LLM for tests: replays responses per node, never touches the network."""

import re
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from marketmind.llm.types import (
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
    StreamDone,
    StreamEvent,
    TextDelta,
)


class FakeCall(BaseModel):
    node: str
    response: LLMResponse
    request: dict[str, Any] | None = None  # kept in recorded fixtures for humans; not matched


class LLMFixture(BaseModel):
    case: str
    calls: list[FakeCall]


class NoScriptedResponseError(AssertionError):
    pass


class FakeLLMProvider:
    """Each node has its own queue, so a fixture only fixes call order within a node."""

    def __init__(self, calls: Iterable[FakeCall] = (), *, case: str = "inline") -> None:
        self.name = "fake"
        self.case = case
        self.requests: list[LLMRequest] = []
        self._queues: defaultdict[str, deque[LLMResponse]] = defaultdict(deque)
        for call in calls:
            self._queues[call.node].append(call.response)

    @classmethod
    def from_fixture(cls, path: Path) -> "FakeLLMProvider":
        fixture = LLMFixture.model_validate_json(path.read_text())
        return cls(fixture.calls, case=fixture.case)

    def script(
        self,
        node: str,
        text: str = "",
        *,
        tool_calls: list[LLMToolCall] | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        self._queues[node].append(
            LLMResponse(
                text=text,
                tool_calls=tool_calls or [],
                usage=usage or LLMUsage(),
                model="fake",
                finish_reason="tool_calls" if tool_calls else "stop",
            )
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        queue = self._queues.get(request.node)
        if not queue:
            raise NoScriptedResponseError(
                f"fixture {self.case!r} has no scripted response left for node {request.node!r}"
            )
        return queue.popleft()

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        response = await self.complete(request)
        for piece in re.findall(r"\S+\s*|\s+", response.text):
            yield TextDelta(text=piece)
        yield StreamDone(response=response)

    def assert_exhausted(self) -> None:
        left = {node: len(q) for node, q in self._queues.items() if q}
        if left:
            raise AssertionError(f"fixture {self.case!r} has unused responses: {left}")
