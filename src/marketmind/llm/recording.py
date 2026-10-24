"""Record mode: wrap a live provider and save what it returned as a replayable fixture."""

from collections.abc import AsyncIterator
from pathlib import Path

from marketmind.llm.base import LLMProvider
from marketmind.llm.fake import FakeCall, LLMFixture
from marketmind.llm.types import LLMRequest, LLMResponse, StreamDone, StreamEvent


class RecordingProvider:
    def __init__(self, inner: LLMProvider, *, case: str, path: Path) -> None:
        self.name = inner.name
        self._inner = inner
        self._case = case
        self._path = path
        self._calls: list[FakeCall] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        response = await self._inner.complete(request)
        self._record(request, response)
        return response

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        async for event in self._inner.stream(request):
            if isinstance(event, StreamDone):
                self._record(request, event.response)
            yield event

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fixture = LLMFixture(case=self._case, calls=self._calls)
        self._path.write_text(fixture.model_dump_json(indent=2) + "\n")

    def _record(self, request: LLMRequest, response: LLMResponse) -> None:
        self._calls.append(
            FakeCall(node=request.node, response=response, request=request.model_dump(mode="json"))
        )
