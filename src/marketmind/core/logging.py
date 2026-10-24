"""structlog JSON logging. Secrets are redacted by key name and by `SecretStr` type."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, TextIO

import structlog
from pydantic import SecretStr

_REDACTED = "[redacted]"
# Matched as the whole key or a `_<word>` suffix, so `openrouter_api_key` is redacted
# while the spec's `tokens_in` / `tokens_out` fields are not.
_SECRET_WORDS = ("api_key", "authorization", "password", "secret", "token")


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(k == w or k.endswith(f"_{w}") for w in _SECRET_WORDS)


def redact_secrets(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key, value in event_dict.items():
        if isinstance(value, SecretStr) or _is_secret_key(key):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(
    level: str = "INFO", *, json: bool = True, stream: TextIO | None = None
) -> None:
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(name)
    return logger
