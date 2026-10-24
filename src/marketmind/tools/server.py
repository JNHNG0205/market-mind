"""MCP tool server. Every external call the runtime makes goes through this process."""

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from marketmind.core.config import Settings


async def healthz(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def build_server() -> MCPServer:
    server = MCPServer("marketmind-tools", version="0.1.0")
    # Registered by call rather than as a decorator: the SDK's decorator is untyped.
    server.custom_route("/healthz", methods=["GET"])(healthz)
    return server


def create_app(settings: Settings | None = None) -> Starlette:
    """Entry point for uvicorn: `uvicorn --factory marketmind.tools.server:create_app`."""
    settings = settings or Settings()
    return build_server().streamable_http_app(streamable_http_path="/mcp", host=settings.mcp_host)
