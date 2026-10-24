import httpx
import pytest
from fastapi import FastAPI

from marketmind.api.app import create_app
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
from marketmind.core.ids import is_ulid


def _app_with_routes() -> FastAPI:
    app = create_app({})

    @app.get("/boom/{kind}")
    async def boom(kind: str) -> None:
        errors: dict[str, AppError] = {
            "bad": BadRequestError("bad input"),
            "missing": NotFoundError("unknown session"),
            "conflict": ConflictError("action already resolved"),
            "limited": RateLimitedError("20 requests a minute"),
            "down": DependencyUnavailableError("redis is down"),
        }
        if kind == "crash":
            raise RuntimeError("secret internal detail")
        raise errors[kind]

    @app.get("/typed")
    async def typed(n: int) -> dict[str, int]:
        return {"n": n}

    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize(
    ("kind", "status", "code"),
    [
        ("bad", 400, "bad_request"),
        ("missing", 404, "not_found"),
        ("conflict", 409, "conflict"),
        ("limited", 429, "rate_limited"),
        ("down", 503, "dependency_unavailable"),
    ],
)
async def test_app_errors_render_the_error_envelope(kind: str, status: int, code: str) -> None:
    async with _client(_app_with_routes()) as client:
        response = await client.get(f"/boom/{kind}")
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["trace_id"] == response.headers["x-trace-id"]
    assert is_ulid(error["trace_id"])


async def test_request_validation_errors_are_400_with_envelope() -> None:
    async with _client(_app_with_routes()) as client:
        response = await client.get("/typed", params={"n": "not-a-number"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


async def test_unhandled_errors_are_500_without_leaking_details() -> None:
    async with _client(_app_with_routes()) as client:
        response = await client.get("/boom/crash")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert error["trace_id"] == response.headers["x-trace-id"]


async def test_every_response_gets_a_fresh_trace_id() -> None:
    async with _client(_app_with_routes()) as client:
        first = await client.get("/healthz")
        second = await client.get("/healthz")
    assert is_ulid(first.headers["x-trace-id"])
    assert first.headers["x-trace-id"] != second.headers["x-trace-id"]


@pytest.mark.parametrize(
    ("code", "retryable"),
    [
        (ToolErrorCode.TIMEOUT, True),
        (ToolErrorCode.RATE_LIMITED, True),
        (ToolErrorCode.UPSTREAM_ERROR, True),
        (ToolErrorCode.BAD_ARGS, False),
        (ToolErrorCode.NOT_FOUND, False),
    ],
)
def test_tool_error_retryable_defaults_follow_the_code(
    code: ToolErrorCode, retryable: bool
) -> None:
    err = ToolError.of(code, "x")
    assert err.retryable is retryable
    assert err.model_dump() == {"code": code.value, "message": "x", "retryable": retryable}


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("GET", "/no-such-route", 404, "not_found"),
        ("POST", "/healthz", 405, "method_not_allowed"),
    ],
)
async def test_framework_http_errors_use_the_envelope_too(
    method: str, path: str, status: int, code: str
) -> None:
    async with _client(_app_with_routes()) as client:
        response = await client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["trace_id"] == response.headers["x-trace-id"]
