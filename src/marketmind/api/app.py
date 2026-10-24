"""FastAPI application factory."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from marketmind.api import readiness
from marketmind.api.errors import install_error_handlers
from marketmind.api.middleware import TraceMiddleware
from marketmind.core.config import Settings
from marketmind.core.logging import configure_logging

ReadinessCheck = Callable[[], Awaitable[None]]


async def _run_check(check: ReadinessCheck, timeout_s: float) -> str:
    try:
        await asyncio.wait_for(check(), timeout=timeout_s)
    except TimeoutError:
        return f"error: timeout after {timeout_s}s"
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"
    return "ok"


def create_app(checks: Mapping[str, ReadinessCheck], timeout_s: float = 2.0) -> FastAPI:
    app = FastAPI(title="MarketMind", version="0.1.0")
    app.add_middleware(TraceMiddleware)
    install_error_handlers(app)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        names = list(checks)
        results = await asyncio.gather(*(_run_check(checks[n], timeout_s) for n in names))
        report = dict(zip(names, results, strict=True))
        ready = all(r == "ok" for r in results)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": report},
        )

    return app


def create_default_app() -> FastAPI:
    """Entry point for uvicorn: `uvicorn --factory marketmind.api.app:create_default_app`."""
    settings = Settings()
    configure_logging(settings.log_level, json=settings.log_json)
    checks: dict[str, ReadinessCheck] = {
        "postgres": lambda: readiness.check_postgres(settings.database_url),
        "redis": lambda: readiness.check_redis(settings.redis_url),
        "mcp": lambda: readiness.check_mcp(settings.mcp_server_url),
    }
    return create_app(checks, timeout_s=settings.readiness_timeout_s)
