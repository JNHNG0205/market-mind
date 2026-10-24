from datetime import UTC, datetime

from marketmind.core.clock import FixedClock, SystemClock
from marketmind.core.config import Settings
from marketmind.core.deps import build_deps


def test_build_deps_defaults_to_the_system_clock() -> None:
    deps = build_deps(Settings(_env_file=None))
    assert isinstance(deps.clock, SystemClock)
    assert deps.settings.llm_provider == "openrouter"


def test_build_deps_accepts_an_injected_clock() -> None:
    clock = FixedClock(datetime(2026, 10, 24, tzinfo=UTC))
    deps = build_deps(Settings(_env_file=None), clock=clock)
    assert deps.clock.now() == datetime(2026, 10, 24, tzinfo=UTC)
