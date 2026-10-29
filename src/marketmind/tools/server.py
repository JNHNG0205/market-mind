from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from marketmind.core.config import Settings


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def build_server() -> MCPServer:
    server = MCPServer("marketmind-tools", version="0.1.0")
    # custom_route has no return annotation, so the @decorator form fails mypy --strict
    # ("untyped decorator"). Calling it directly registers the same Route.
    server.custom_route("/healthz", methods=["GET"])(healthz)
    return server


def create_app(settings: Settings | None = None) -> Starlette:
    if settings is None:
        settings = Settings()
    # A fresh MCPServer per app: its session manager can only run once per instance.
    return build_server().streamable_http_app(streamable_http_path="/mcp", host=settings.mcp_host)
