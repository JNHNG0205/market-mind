import httpx
import pytest
import respx

from marketmind.api.readiness import check_mcp, libpq_dsn, mcp_health_url


def test_libpq_dsn_strips_driver() -> None:
    assert (
        libpq_dsn("postgresql+psycopg://u:p@db:5432/marketmind")
        == "postgresql://u:p@db:5432/marketmind"
    )
    assert libpq_dsn("postgresql://u:p@db/x") == "postgresql://u:p@db/x"


def test_mcp_health_url() -> None:
    assert mcp_health_url("http://mcp-tools:8001/mcp") == "http://mcp-tools:8001/healthz"


@respx.mock
async def test_check_mcp_ok() -> None:
    respx.get("http://mcp-tools:8001/healthz").mock(return_value=httpx.Response(200))
    await check_mcp("http://mcp-tools:8001/mcp")


@respx.mock
async def test_check_mcp_down() -> None:
    respx.get("http://mcp-tools:8001/healthz").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await check_mcp("http://mcp-tools:8001/mcp")
