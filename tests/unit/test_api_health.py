import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from marketmind.api.app import ReadinessCheck, create_app


async def _ok() -> None:
    return None


async def _down() -> None:
    raise ConnectionError("connection refused")


async def _hangs() -> None:
    await asyncio.sleep(10)


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def healthy_client() -> AsyncIterator[httpx.AsyncClient]:
    checks: dict[str, ReadinessCheck] = {"postgres": _ok, "redis": _ok, "mcp": _ok}
    async with _client(create_app(checks)) as client:
        yield client


async def test_healthz_is_ok_without_touching_dependencies() -> None:
    async with _client(create_app({"postgres": _down})) as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_is_ready_when_all_checks_pass(healthy_client: httpx.AsyncClient) -> None:
    response = await healthy_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "redis": "ok", "mcp": "ok"},
    }


async def test_readyz_is_503_and_names_the_failing_dependency() -> None:
    app = create_app({"postgres": _ok, "redis": _down, "mcp": _ok})
    async with _client(app) as client:
        response = await client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "error: ConnectionError: connection refused"


async def test_readyz_times_out_a_hanging_check() -> None:
    app = create_app({"postgres": _hangs, "redis": _ok}, timeout_s=0.05)
    async with _client(app) as client:
        response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] == "error: timeout after 0.05s"
