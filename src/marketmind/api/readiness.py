import urllib.parse

import httpx
import psycopg
import redis.asyncio as redis


def libpq_dsn(database_url: str) -> str:
    return database_url.replace("+psycopg", "")


def mcp_health_url(mcp_server_url: str) -> str:
    parts = urllib.parse.urlparse(mcp_server_url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/healthz", "", ""))


async def check_postgres(database_url: str) -> None:
    async with await psycopg.AsyncConnection.connect(libpq_dsn(database_url)) as conn:
        await conn.execute("SELECT 1")


async def check_redis(redis_url: str) -> None:
    async with redis.from_url(redis_url) as client:
        await client.ping()


async def check_mcp(mcp_server_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(mcp_health_url(mcp_server_url))
        response.raise_for_status()
