import pytest
from pydantic import ValidationError

from marketmind.core.errors import ToolError, ToolErrorCode


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
