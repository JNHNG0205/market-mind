"""Builds the configured `LLMProvider` from settings."""

from typing import Any

import httpx2
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from marketmind.core.config import Settings
from marketmind.core.errors import ConfigError
from marketmind.llm.anthropic_provider import AnthropicProvider
from marketmind.llm.base import LLMProvider
from marketmind.llm.fake import FakeLLMProvider
from marketmind.llm.fallback import FallbackProvider
from marketmind.llm.openai_compat import OpenAICompatProvider


def build_llm(settings: Settings, *, http_client: httpx2.AsyncClient | None = None) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "anthropic":
        return _anthropic(settings, http_client)
    return _openrouter(settings, http_client)


def _openrouter(settings: Settings, http_client: httpx2.AsyncClient | None) -> LLMProvider:
    if settings.openrouter_api_key is None:
        raise ConfigError("LLM_PROVIDER=openrouter needs OPENROUTER_API_KEY")
    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        default_headers={"X-Title": "MarketMind"},
        http_client=http_client,
    )
    pin: dict[str, Any] = {}
    if settings.openrouter_provider_order:
        pin = {"provider": {"order": settings.openrouter_provider_order, "allow_fallbacks": False}}
    primary = OpenAICompatProvider(client, extra_body=pin)
    if settings.llm_fallback_model is None:
        return primary
    # The fallback model runs on whichever host OpenRouter picks (D7).
    return FallbackProvider(primary, OpenAICompatProvider(client), settings.llm_fallback_model)


def _anthropic(settings: Settings, http_client: httpx2.AsyncClient | None) -> LLMProvider:
    if settings.anthropic_api_key is None:
        raise ConfigError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        http_client=http_client,
    )
    return AnthropicProvider(client, effort=settings.anthropic_effort)
