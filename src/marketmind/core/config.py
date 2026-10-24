"""Application settings, read from the environment (and `.env` in dev)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://marketmind:marketmind@localhost:5432/marketmind"
    redis_url: str = "redis://localhost:6379/0"
    mcp_server_url: str = "http://localhost:8001/mcp"
    # Bind host for the MCP server. DNS-rebinding protection is on for localhost binds,
    # so containers set 0.0.0.0 to accept the `mcp-tools` hostname.
    mcp_host: str = "127.0.0.1"
    readiness_timeout_s: float = 2.0
