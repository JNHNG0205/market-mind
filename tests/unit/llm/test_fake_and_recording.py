from pathlib import Path

import pytest

from marketmind.llm.fake import FakeCall, FakeLLMProvider, LLMFixture, NoScriptedResponseError
from marketmind.llm.recording import RecordingProvider
from marketmind.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    StreamDone,
    TextDelta,
)


def _req(node: str, text: str = "q") -> LLMRequest:
    return LLMRequest(node=node, model="m", messages=[LLMMessage(role="user", content=text)])


def _resp(text: str) -> LLMResponse:
    return LLMResponse(text=text, model="m", finish_reason="stop")


async def test_responses_are_served_per_node_in_script_order() -> None:
    fake = FakeLLMProvider(
        [
            FakeCall(node="router", response=_resp("r1")),
            FakeCall(node="planner", response=_resp("p1")),
            FakeCall(node="router", response=_resp("r2")),
        ]
    )
    assert (await fake.complete(_req("planner"))).text == "p1"
    assert (await fake.complete(_req("router"))).text == "r1"
    assert (await fake.complete(_req("router"))).text == "r2"
    assert [r.node for r in fake.requests] == ["planner", "router", "router"]
    fake.assert_exhausted()


async def test_running_out_of_script_names_the_node() -> None:
    fake = FakeLLMProvider([FakeCall(node="router", response=_resp("r1"))])
    with pytest.raises(NoScriptedResponseError, match="'composer'"):
        await fake.complete(_req("composer"))


def test_assert_exhausted_lists_unused_calls() -> None:
    fake = FakeLLMProvider([FakeCall(node="router", response=_resp("r1"))])
    with pytest.raises(AssertionError, match="router"):
        fake.assert_exhausted()


async def test_script_helper_builds_text_and_tool_call_responses() -> None:
    fake = FakeLLMProvider()
    call = LLMToolCall(id="c1", name="get_price", arguments={"symbol": "BTCUSDT"})
    fake.script("planner", tool_calls=[call])
    response = await fake.complete(_req("planner"))
    assert response.tool_calls == [call]
    assert response.finish_reason == "tool_calls"


async def test_stream_replays_text_as_deltas_then_done() -> None:
    fake = FakeLLMProvider()
    fake.script("composer", "BTC is at 100 [1].")
    events = [e async for e in fake.stream(_req("composer"))]
    deltas = [e.text for e in events if isinstance(e, TextDelta)]
    assert "".join(deltas) == "BTC is at 100 [1]."
    assert len(deltas) > 1
    assert isinstance(events[-1], StreamDone)
    assert events[-1].response.text == "BTC is at 100 [1]."


async def test_recording_saves_a_fixture_that_replays_identically(tmp_path: Path) -> None:
    live = FakeLLMProvider()  # stands in for a real provider
    live.script("router", '{"intent": "price_lookup"}')
    live.script("composer", "streamed answer")

    path = tmp_path / "case.json"
    recorder = RecordingProvider(live, case="btc_price", path=path)
    first = await recorder.complete(_req("router", "btc price?"))
    streamed = [e async for e in recorder.stream(_req("composer"))]
    recorder.save()

    fixture = LLMFixture.model_validate_json(path.read_text())
    assert fixture.case == "btc_price"
    assert [c.node for c in fixture.calls] == ["router", "composer"]
    assert fixture.calls[0].request is not None
    assert fixture.calls[0].request["messages"][0]["content"] == "btc price?"

    replay = FakeLLMProvider.from_fixture(path)
    assert await replay.complete(_req("router")) == first
    done = streamed[-1]
    assert isinstance(done, StreamDone)
    replayed = [e async for e in replay.stream(_req("composer"))]
    assert replayed[-1] == done
