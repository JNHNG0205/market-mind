"""Error types: structured tool errors (returned, never raised) and API errors (raised)."""

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import BaseModel


class ToolErrorCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    BAD_ARGS = "bad_args"
    UPSTREAM_ERROR = "upstream_error"
    NOT_FOUND = "not_found"


_RETRYABLE = {ToolErrorCode.TIMEOUT, ToolErrorCode.RATE_LIMITED, ToolErrorCode.UPSTREAM_ERROR}


class ToolError(BaseModel):
    code: ToolErrorCode
    message: str
    retryable: bool

    @classmethod
    def of(cls, code: ToolErrorCode, message: str) -> Self:
        return cls(code=code, message=message, retryable=code in _RETRYABLE)


class AppError(Exception):
    """Base for errors the API renders as `{"error": {"code", "message", "trace_id"}}`."""

    code: ClassVar[str] = "internal_error"
    http_status: ClassVar[int] = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    code = "bad_request"
    http_status = 400


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404


class ConflictError(AppError):
    code = "conflict"
    http_status = 409


class RateLimitedError(AppError):
    code = "rate_limited"
    http_status = 429


class DependencyUnavailableError(AppError):
    code = "dependency_unavailable"
    http_status = 503
