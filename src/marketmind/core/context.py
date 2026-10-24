"""Request-scoped context: the trace id plus fields bound onto every log line."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import structlog

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def current_trace_id() -> str | None:
    return _trace_id.get()


@contextmanager
def request_context(trace_id: str, **fields: str) -> Iterator[None]:
    token = _trace_id.set(trace_id)
    with structlog.contextvars.bound_contextvars(trace_id=trace_id, **fields):
        try:
            yield
        finally:
            _trace_id.reset(token)
