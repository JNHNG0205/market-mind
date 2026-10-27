import asyncio

import httpx

from marketmind.api.app import create_app


async def ok() -> None:
    return None


async def down() -> None:
    raise ConnectionRefusedError("connection refused")


async def hangs() -> None:
    await asyncio.sleep(10)


async def test_api_healthz() -> None:
    app = create_app({"postgres": ok, "redis": ok, "mcp": ok})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get("http://test/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_api_readyz() -> None:
    app = create_app({"postgres": ok, "redis": ok, "mcp": ok})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get("http://test/readyz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "redis": "ok", "mcp": "ok"},
    }


async def test_api_readyz_failure() -> None:
    app = create_app({"postgres": down, "redis": ok, "mcp": ok})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get("http://test/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "postgres": "error: ConnectionRefusedError: connection refused",
            "redis": "ok",
            "mcp": "ok",
        },
    }


async def test_api_readyz_timeout() -> None:
    app = create_app({"postgres": hangs, "redis": ok, "mcp": ok}, timeout_s=0.05)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get("http://test/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"postgres": "error: timeout after 0.05s", "redis": "ok", "mcp": "ok"},
    }
