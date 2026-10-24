"""Secondary-provider fallback (SPEC §13; DECISIONS.md D7).

The SDKs already retry 429/5xx twice; this wrapper only runs once those retries are spent.
"""

from collections.abc import AsyncIterator

from marketmind.core.logging import get_logger
from marketmind.llm.base import LLMProvider
from marketmind.llm.types import LLMError, LLMRequest, LLMResponse, StreamEvent


class FallbackProvider:
    def __init__(self, primary: LLMProvider, fallback: LLMProvider, fallback_model: str) -> None:
        self.name = primary.name
        self._primary = primary
        self._fallback = fallback
        self._fallback_model = fallback_model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            return await self._primary.complete(request)
        except LLMError as exc:
            if not exc.retryable:
                raise
            return await self._fallback.complete(self._switch(request, exc))

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        started = False
        try:
            async for event in self._primary.stream(request):
                started = True
                yield event
            return
        except LLMError as exc:
            # Once text has reached the client, switching models would splice two answers.
            if started or not exc.retryable:
                raise
            fallback_request = self._switch(request, exc)
        async for event in self._fallback.stream(fallback_request):
            yield event

    def _switch(self, request: LLMRequest, exc: LLMError) -> LLMRequest:
        get_logger().warning(
            "llm_fallback",
            node=request.node,
            model=request.model,
            fallback_model=self._fallback_model,
            error=str(exc),
        )
        return request.model_copy(update={"model": self._fallback_model})
