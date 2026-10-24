from starlette.testclient import TestClient

from marketmind.core.config import Settings
from marketmind.tools.server import create_app


def test_tool_server_healthz() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tool_server_mounts_the_mcp_endpoint() -> None:
    # A bare GET without MCP headers is rejected by the transport, which proves the route exists.
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/mcp")
    assert response.status_code != 404
