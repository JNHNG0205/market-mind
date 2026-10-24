"""Application settings, read from the environment (and `.env` in dev)."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash-1017"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True

    # Data stores and the tool server
    database_url: str = "postgresql+psycopg://marketmind:marketmind@localhost:5432/marketmind"
    redis_url: str = "redis://localhost:6379/0"
    mcp_server_url: str = "http://localhost:8001/mcp"
    # Bind host for the MCP server. DNS-rebinding protection is on for localhost binds,
    # so containers set 0.0.0.0 to accept the `mcp-tools` hostname.
    mcp_host: str = "127.0.0.1"
    readiness_timeout_s: float = 2.0

    # LLMs (DECISIONS.md D3-D7)
    llm_provider: Literal["openrouter", "anthropic", "fake"] = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    llm_model_router: str = _DEFAULT_MODEL
    llm_model_planner: str = _DEFAULT_MODEL
    llm_model_composer: str = _DEFAULT_MODEL
    llm_fallback_model: str | None = "z-ai/glm-5.3-flash"
    # Hosts the primary model may use, tried in order (D37). Empty means unpinned.
    openrouter_provider_order: list[str] = ["Fireworks", "Together"]
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2  # SDK retries on 429/5xx before falling back
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"

    # Embeddings (D8, used from M2)
    embedding_provider: Literal["openrouter", "local"] = "openrouter"
    embedding_model: str = "openai/text-embedding-3-small"

    # Tools
    search_provider: Literal["tavily", "brave"] = "tavily"
    tavily_api_key: SecretStr | None = None
    market_data_provider: Literal["exchange", "coingecko"] = "exchange"
    coingecko_api_key: SecretStr | None = None

    # Agent
    router_fast_path_min_sim: float = 0.85
    router_fast_path_min_margin: float = 0.10
    agent_max_steps: int = 6
    agent_max_tool_calls: int = 12
