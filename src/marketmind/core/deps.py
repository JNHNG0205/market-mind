"""Dependency container handed to every graph node. Later steps add MCP client and repos."""

from dataclasses import dataclass

from marketmind.core.clock import Clock, SystemClock
from marketmind.core.config import Settings
from marketmind.llm.base import LLMProvider
from marketmind.llm.factory import build_llm


@dataclass(frozen=True, slots=True)
class Deps:
    settings: Settings
    clock: Clock
    llm: LLMProvider


def build_deps(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    llm: LLMProvider | None = None,
) -> Deps:
    settings = settings or Settings()
    return Deps(
        settings=settings,
        clock=clock or SystemClock(),
        llm=llm or build_llm(settings),
    )
