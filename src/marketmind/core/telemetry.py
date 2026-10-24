"""Tracing hook. Today `span` only logs; P3 swaps the body for OpenTelemetry."""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from marketmind.core.logging import get_logger


@contextmanager
def span(name: str, **attrs: object) -> Iterator[dict[str, object]]:
    """Time a block and log one `span` event. Callers may add fields to the yielded dict."""
    fields: dict[str, object] = dict(attrs)
    start = time.perf_counter()
    try:
        yield fields
    except Exception as exc:
        fields.update(ok=False, error=type(exc).__name__)
        raise
    else:
        fields["ok"] = True
    finally:
        fields["latency_ms"] = round((time.perf_counter() - start) * 1000)
        get_logger().info("span", span=name, **fields)
