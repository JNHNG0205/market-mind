"""Record/replay round trip. Replays tests/fixtures/llm/json_classification.json offline;
`RECORD_LLM=1 uv run pytest tests/unit/llm/test_llm_case_fixture.py` re-records it live."""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from marketmind.core.config import Settings
from marketmind.llm.base import LLMProvider
from marketmind.llm.structured import complete_json
from marketmind.llm.types import LLMMessage, LLMRequest


class Topic(BaseModel):
    topic: Literal["crypto", "other"]


async def test_recorded_json_classification_replays(
    llm_case: Callable[[str], LLMProvider],
) -> None:
    llm = llm_case("json_classification")
    request = LLMRequest(
        node="router",
        model=Settings(_env_file=None).llm_model_router,
        messages=[
            LLMMessage(role="system", content="Classify whether the user asks about crypto."),
            LLMMessage(role="user", content="What is BTC trading at?"),
        ],
        temperature=0,
        max_tokens=256,
    )
    result = await complete_json(llm, request, Topic)
    assert result.value.topic == "crypto"
