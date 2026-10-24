from datetime import UTC, datetime, timedelta

import pytest

from marketmind.core.clock import Clock, FixedClock, SystemClock
from marketmind.core.ids import is_ulid, new_id


def test_system_clock_is_timezone_aware_utc() -> None:
    clock: Clock = SystemClock()
    assert clock.now().tzinfo is UTC


def test_fixed_clock_returns_its_instant_and_advances() -> None:
    at = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    clock = FixedClock(at)
    assert clock.now() == at
    clock.advance(timedelta(minutes=5))
    assert clock.now() == datetime(2026, 10, 24, 12, 5, tzinfo=UTC)


def test_fixed_clock_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 10, 24, 12, 0))


def test_fixed_clock_normalises_other_timezones_to_utc() -> None:
    from zoneinfo import ZoneInfo

    clock = FixedClock(datetime(2026, 10, 24, 20, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur")))
    assert clock.now() == datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    assert clock.now().tzinfo is UTC


def test_new_id_is_a_unique_ulid() -> None:
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000
    assert all(is_ulid(i) and len(i) == 26 for i in ids)


@pytest.mark.parametrize("value", ["", "not-a-ulid", "01M5PBCCGBH6D0RAXTRF6P0VH", "u" * 26])
def test_is_ulid_rejects_malformed_values(value: str) -> None:
    assert not is_ulid(value)
