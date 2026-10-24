"""Dependency probes used by `/readyz`. Each raises on failure and returns None on success."""

from urllib.parse import urlsplit, urlunsplit

import httpx
import psycopg
import redis.asyncio as redis


def libpq_dsn(database_url: str) -> str:
    """Turn a SQLAlchemy URL (`postgresql+psycopg://...`) into a plain libpq DSN."""
    scheme, rest = database_url.split("://", 1)
    return f"{scheme.split('+', 1)[0]}://{rest}"


def mcp_health_url(mcp_server_url: str) -> str:
    parts = urlsplit(mcp_server_url)
    return urlunsplit((parts.scheme, parts.netloc, "/healthz", "", ""))


async def check_postgres(database_url: str, require_extension: str | None = None) -> None:
    async with await psycopg.AsyncConnection.connect(libpq_dsn(database_url)) as conn:
        await conn.execute("SELECT 1")
        if require_extension is not None:
            cur = await conn.execute(
                "SELECT 1 FROM pg_available_extensions WHERE name = %s", (require_extension,)
            )
            if await cur.fetchone() is None:
                raise RuntimeError(f"extension {require_extension!r} is not available")


async def check_redis(redis_url: str) -> None:
    client = redis.from_url(redis_url)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def check_mcp(mcp_server_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(mcp_health_url(mcp_server_url))
        response.raise_for_status()
