"""Dependency container handed to every graph node. Later steps add LLM, MCP client and repos."""

from dataclasses import dataclass

from marketmind.core.clock import Clock, SystemClock
from marketmind.core.config import Settings


@dataclass(frozen=True, slots=True)
class Deps:
    settings: Settings
    clock: Clock


def build_deps(settings: Settings | None = None, *, clock: Clock | None = None) -> Deps:
    return Deps(settings=settings or Settings(), clock=clock or SystemClock())
