import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from marketmind.core.config import Settings
from marketmind.llm.base import LLMProvider
from marketmind.llm.factory import build_llm
from marketmind.llm.fake import FakeLLMProvider
from marketmind.llm.recording import RecordingProvider

LLM_FIXTURES = Path(__file__).parent / "fixtures" / "llm"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("LIVE_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live test: set LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def llm_case() -> Iterator[Callable[[str], LLMProvider]]:
    """`llm_case("name")` replays tests/fixtures/llm/name.json and asserts every scripted
    response was used. With RECORD_LLM=1 it calls the real provider and rewrites the file."""
    opened: list[FakeLLMProvider | RecordingProvider] = []

    def open_case(case: str) -> LLMProvider:
        path = LLM_FIXTURES / f"{case}.json"
        provider: FakeLLMProvider | RecordingProvider
        if os.environ.get("RECORD_LLM") == "1":
            provider = RecordingProvider(build_llm(Settings()), case=case, path=path)
        else:
            provider = FakeLLMProvider.from_fixture(path)
        opened.append(provider)
        return provider

    yield open_case
    for provider in opened:
        if isinstance(provider, RecordingProvider):
            provider.save()
        else:
            provider.assert_exhausted()
