from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://marketmind:marketmind@localhost:5432/marketmind"

    redis_url: str = "redis://localhost:6379/0"
    mcp_server_url: str = "http://localhost:8001/mcp"

    mcp_host: str = "127.0.0.1"

    readiness_timeout_s: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
