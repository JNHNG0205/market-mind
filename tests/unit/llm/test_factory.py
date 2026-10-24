import json
from typing import Any

import httpx2
import pytest

from marketmind.core.config import Settings
from marketmind.core.errors import ConfigError
from marketmind.llm.anthropic_provider import AnthropicProvider
from marketmind.llm.factory import build_llm
from marketmind.llm.fake import FakeLLMProvider
from marketmind.llm.openai_compat import OpenAICompatProvider
from marketmind.llm.types import LLMMessage, LLMRequest


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_fake_provider() -> None:
    assert isinstance(build_llm(_settings(llm_provider="fake")), FakeLLMProvider)


@pytest.mark.parametrize(
    ("provider", "env"), [("openrouter", "OPENROUTER_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")]
)
def test_missing_key_is_a_clear_config_error(provider: str, env: str) -> None:
    with pytest.raises(ConfigError, match=env):
        build_llm(_settings(llm_provider=provider))


def test_anthropic_provider() -> None:
    llm = build_llm(_settings(llm_provider="anthropic", anthropic_api_key="sk-ant-test"))
    assert isinstance(llm, AnthropicProvider)


def test_openrouter_without_fallback_model_is_a_single_provider() -> None:
    llm = build_llm(_settings(openrouter_api_key="sk-or-test", llm_fallback_model=None))
    assert isinstance(llm, OpenAICompatProvider)


async def test_openrouter_pins_the_primary_host_and_falls_back_unpinned() -> None:
    seen: list[tuple[dict[str, Any], httpx2.Headers]] = []
    replies = [
        httpx2.Response(503, json={"error": {"message": "DeepSeek host down"}}),
        httpx2.Response(
            200,
            json={
                "id": "g",
                "object": "chat.completion",
                "created": 1,
                "model": "z-ai/glm-5.3-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
        ),
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((json.loads(request.content), request.headers))
        return replies.pop(0)

    settings = _settings(openrouter_api_key="sk-or-test", llm_max_retries=0)
    llm = build_llm(
        settings, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    request = LLMRequest(
        node="router",
        model=settings.llm_model_router,
        messages=[LLMMessage(role="user", content="q")],
    )
    response = await llm.complete(request)

    assert response.text == "ok"
    (primary_body, primary_headers), (fallback_body, _) = seen
    assert primary_body["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert primary_body["provider"] == {
        "order": ["Fireworks", "Together"],
        "allow_fallbacks": False,
    }
    assert primary_headers["authorization"] == "Bearer sk-or-test"
    assert primary_headers["x-title"] == "MarketMind"
    assert fallback_body["model"] == "z-ai/glm-5.3-flash"
    assert "provider" not in fallback_body
