import asyncio
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from marketmind.api.readiness import check_mcp, check_postgres, check_redis
from marketmind.core.config import Settings


async def _run_check(check: Callable[[], Awaitable[None]], timeout_s: float) -> str:
    try:
        await asyncio.wait_for(check(), timeout=timeout_s)
        return "ok"
    except TimeoutError:
        return f"error: timeout after {timeout_s}s"
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"


def create_app(
    checks: Mapping[str, Callable[[], Awaitable[None]]], timeout_s: float = 2.0
) -> FastAPI:
    app = FastAPI()

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse(content={"status": "ok"})

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        check_results = await asyncio.gather(
            *[_run_check(check, timeout_s) for check in checks.values()]
        )
        report = dict(zip(checks, check_results, strict=True))
        if all(result == "ok" for result in check_results):
            return JSONResponse(content={"status": "ready", "checks": report}, status_code=200)
        else:
            return JSONResponse(content={"status": "not_ready", "checks": report}, status_code=503)

    return app


def create_default_app() -> FastAPI:
    settings = Settings()
    checks = {
        "postgres": lambda: check_postgres(settings.database_url),
        "redis": lambda: check_redis(settings.redis_url),
        "mcp": lambda: check_mcp(settings.mcp_server_url),
    }
    return create_app(checks, timeout_s=settings.readiness_timeout_s)
