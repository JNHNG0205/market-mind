from enum import StrEnum
from typing import Self

from pydantic import BaseModel


class ToolErrorCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    BAD_ARGS = "bad_args"
    UPSTREAM_ERROR = "upstream_error"
    NOT_FOUND = "not_found"


_RETRYABLE = frozenset(
    {ToolErrorCode.TIMEOUT, ToolErrorCode.RATE_LIMITED, ToolErrorCode.UPSTREAM_ERROR}
)


class ToolError(BaseModel):
    code: ToolErrorCode
    message: str
    retryable: bool

    @classmethod
    def of(cls, code: ToolErrorCode, message: str) -> Self:
        return cls(code=code, message=message, retryable=code in _RETRYABLE)
