from pathlib import Path

import pytest

from marketmind.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_defaults_follow_the_planning_decisions() -> None:
    s = Settings(_env_file=None)
    assert s.llm_provider == "openrouter"
    assert s.llm_base_url == "https://openrouter.ai/api/v1"
    assert s.llm_model_router == "deepseek/deepseek-v4.1-flash-1017"
    assert s.llm_model_planner == "deepseek/deepseek-v4.1-flash-1017"
    assert s.llm_model_composer == "deepseek/deepseek-v4.1-flash-1017"
    assert s.llm_fallback_model == "z-ai/glm-5.3-flash"
    assert s.market_data_provider == "exchange"
    assert s.search_provider == "tavily"
    assert s.router_fast_path_min_sim == 0.85
    assert s.router_fast_path_min_margin == 0.10
    assert s.agent_max_steps == 6
    assert s.agent_max_tool_calls == 12


def test_env_example_parses_cleanly() -> None:
    # Guards against .env.example drifting from Settings (inline comments, bad enum values).
    s = Settings(_env_file=REPO_ROOT / ".env.example")
    assert s.llm_provider == "openrouter"
    assert s.market_data_provider == "exchange"
    assert s.database_url.startswith("postgresql+psycopg://")


def test_api_keys_never_appear_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-super-secret")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-super-secret")
    s = Settings(_env_file=None)
    assert s.openrouter_api_key is not None
    assert s.openrouter_api_key.get_secret_value() == "sk-or-super-secret"
    assert "super-secret" not in repr(s)
    assert "super-secret" not in str(s.model_dump())


def test_invalid_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "carrier-pigeon")
    with pytest.raises(ValueError, match="llm_provider"):
        Settings(_env_file=None)
