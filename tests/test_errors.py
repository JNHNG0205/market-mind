import pytest
from pydantic import ValidationError

from marketmind.core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    DependencyUnavailableError,
    NotFoundError,
    RateLimitedError,
    ToolError,
    ToolErrorCode,
)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (ToolErrorCode.TIMEOUT, True),
        (ToolErrorCode.RATE_LIMITED, True),
        (ToolErrorCode.BAD_ARGS, False),
        (ToolErrorCode.UPSTREAM_ERROR, True),
        (ToolErrorCode.NOT_FOUND, False),
    ],
)
def test_retryable_follows_code(code: ToolErrorCode, expected: bool) -> None:
    error = ToolError.of(code, "x")
    assert error.retryable == expected


def test_code_to_json() -> None:
    error = ToolError.of(ToolErrorCode.TIMEOUT, "x")
    assert error.model_dump(mode="json") == {
        "code": "timeout",
        "message": "x",
        "retryable": True,
    }


def test_unknown_code_rejected() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        ToolError(code="oops", message="x", retryable=False)


@pytest.mark.parametrize(
    ("error_class", "code", "http_status"),
    [
        (AppError, "internal_error", 500),
        (BadRequestError, "bad_request", 400),
        (NotFoundError, "not_found", 404),
        (ConflictError, "conflict", 409),
        (RateLimitedError, "rate_limited", 429),
        (DependencyUnavailableError, "dependency_unavailable", 503),
    ],
)
def test_app_error(error_class: type[AppError], code: str, http_status: int) -> None:
    assert error_class.code == code
    assert error_class.http_status == http_status
    assert issubclass(error_class, AppError)
    message = "session abc not found"
    error = error_class(message)
    assert str(error) == message
    assert error.message == message
