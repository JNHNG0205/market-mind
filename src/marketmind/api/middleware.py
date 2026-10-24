"""Per-request trace id, access log and last-resort 500 handling.

Pure ASGI rather than `BaseHTTPMiddleware`, so SSE responses stream untouched and the
trace context stays bound for the whole response.
"""

import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from marketmind.api.errors import error_response
from marketmind.core.context import request_context
from marketmind.core.ids import new_id
from marketmind.core.logging import get_logger

TRACE_HEADER = "x-trace-id"


class TraceMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = new_id()
        log = get_logger()
        started = False
        status = 500
        start = time.perf_counter()

        async def send_with_trace(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message).append(TRACE_HEADER, trace_id)
            await send(message)

        with request_context(trace_id):
            try:
                await self.app(scope, receive, send_with_trace)
            except Exception:
                log.exception("unhandled_error")
                if started:
                    raise
                response = error_response(500, "internal_error", "internal server error")
                await response(scope, receive, send_with_trace)
            finally:
                log.info(
                    "request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status,
                    latency_ms=round((time.perf_counter() - start) * 1000),
                )
