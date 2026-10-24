"""The one interface every node talks to."""

from collections.abc import AsyncIterator
from typing import Protocol

from marketmind.llm.types import LLMRequest, LLMResponse, StreamEvent


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """One completion. Raises `LLMError` on provider failure."""
        ...

    def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        """`TextDelta`s as they arrive, then exactly one `StreamDone` with the full response."""
        ...
