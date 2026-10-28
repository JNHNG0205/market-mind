import httpx
import psycopg
import pytest

from marketmind.api.app import create_default_app
from marketmind.api.readiness import check_postgres, check_redis, libpq_dsn
from marketmind.core.config import Settings

pytestmark = pytest.mark.integration


async def test_readiness_postgres() -> None:
    settings = Settings()
    await check_postgres(settings.database_url)


async def test_readiness_pgvector() -> None:
    settings = Settings()
    async with await psycopg.AsyncConnection.connect(libpq_dsn(settings.database_url)) as conn:
        cursor = await conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        row = await cursor.fetchone()
        assert row is not None


async def test_readiness_redis() -> None:
    settings = Settings()
    await check_redis(settings.redis_url)


async def test_readyz() -> None:
    app = create_default_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/readyz")
        assert response.status_code == 503
        body = response.json()
        # todo: mcp-tools is not in compose yet
        assert body["status"] == "not_ready"
        assert body["checks"]["postgres"] == "ok"
        assert body["checks"]["redis"] == "ok"
        assert body["checks"]["mcp"].startswith("error: ConnectError:")
