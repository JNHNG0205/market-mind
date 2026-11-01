from starlette.testclient import TestClient

from marketmind.core.config import Settings
from marketmind.tools.server import create_app


def test_tool_server_healthz() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_mcp_mounted() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        response = client.get("/mcp")
        assert response.status_code != 404
