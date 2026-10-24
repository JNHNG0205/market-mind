import io
import json
from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from marketmind.core.context import current_trace_id, request_context
from marketmind.core.logging import configure_logging, get_logger
from marketmind.core.telemetry import span


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    configure_logging("DEBUG", stream=stream)
    yield stream
    configure_logging("INFO")


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_logs_are_json_with_level_timestamp_and_bound_context(log_stream: io.StringIO) -> None:
    with request_context("01M5PBCCGBH6D0RAXTRF6P0VHN", session_id="s1"):
        get_logger().info("hello", node="router")
    [line] = _lines(log_stream)
    assert line["event"] == "hello"
    assert line["level"] == "info"
    assert line["trace_id"] == "01M5PBCCGBH6D0RAXTRF6P0VHN"
    assert line["session_id"] == "s1"
    assert line["node"] == "router"
    assert str(line["timestamp"]).endswith("Z")


def test_request_context_is_cleared_on_exit(log_stream: io.StringIO) -> None:
    with request_context("01M5PBCCGBH6D0RAXTRF6P0VHN"):
        assert current_trace_id() == "01M5PBCCGBH6D0RAXTRF6P0VHN"
    assert current_trace_id() is None
    get_logger().info("after")
    assert "trace_id" not in _lines(log_stream)[0]


def test_secrets_are_redacted_but_token_counts_are_not(log_stream: io.StringIO) -> None:
    get_logger().info(
        "call",
        api_key="sk-or-leak",
        openrouter_api_key="sk-or-leak",
        authorization="Bearer leak",
        key=SecretStr("leak"),
        tokens_in=120,
        tokens_out=40,
    )
    [line] = _lines(log_stream)
    assert "leak" not in json.dumps(line)
    assert line["api_key"] == "[redacted]"
    assert line["tokens_in"] == 120
    assert line["tokens_out"] == 40


def test_level_filtering_drops_debug_at_info() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    get_logger().debug("full prompt here")
    assert stream.getvalue() == ""


def test_span_logs_latency_and_extra_attributes(log_stream: io.StringIO) -> None:
    with span("route", node="router") as attrs:
        attrs["intent"] = "price_lookup"
    [line] = _lines(log_stream)
    assert line["event"] == "span"
    assert line["span"] == "route"
    assert line["ok"] is True
    assert line["intent"] == "price_lookup"
    assert isinstance(line["latency_ms"], int)


def test_span_logs_failure_and_reraises(log_stream: io.StringIO) -> None:
    with pytest.raises(RuntimeError), span("plan"):
        raise RuntimeError("boom")
    [line] = _lines(log_stream)
    assert line["ok"] is False
    assert line["error"] == "RuntimeError"
