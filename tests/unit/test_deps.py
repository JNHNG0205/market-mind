from datetime import UTC, datetime

from marketmind.core.clock import FixedClock, SystemClock
from marketmind.core.config import Settings
from marketmind.core.deps import build_deps
from marketmind.llm.fake import FakeLLMProvider


def _settings() -> Settings:
    return Settings(_env_file=None, llm_provider="fake")


def test_build_deps_defaults_to_the_system_clock_and_configured_llm() -> None:
    deps = build_deps(_settings())
    assert isinstance(deps.clock, SystemClock)
    assert isinstance(deps.llm, FakeLLMProvider)


def test_build_deps_accepts_injected_clock_and_llm() -> None:
    clock = FixedClock(datetime(2026, 10, 24, tzinfo=UTC))
    llm = FakeLLMProvider()
    deps = build_deps(_settings(), clock=clock, llm=llm)
    assert deps.clock.now() == datetime(2026, 10, 24, tzinfo=UTC)
    assert deps.llm is llm
