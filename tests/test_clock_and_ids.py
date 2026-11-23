from datetime import UTC, datetime, timedelta, timezone

import pytest

from marketmind.core.clock import Clock, FixedClock, SystemClock
from marketmind.core.ids import is_ulid, new_id


def _read(clock: Clock) -> datetime:
    return clock.now()


def test_fixed_clock_rejects_naive() -> None:
    with pytest.raises(
        ValueError, match="FixedClock must be initialized with a timezone-aware datetime"
    ):
        FixedClock(datetime(2026, 1, 1))


def test_fixed_clock_to_utc() -> None:
    at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    clock = FixedClock(at)
    assert clock.now().utcoffset() == timedelta(0)
    assert at == clock.now()


def test_fixed_clock_advance() -> None:
    t = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    clock = FixedClock(t)
    clock.advance(timedelta(minutes=5))
    assert datetime(2026, 1, 1, 0, 5, 0, tzinfo=UTC) == clock.now()


def test_system_clock_utc() -> None:
    clock = SystemClock()
    assert clock.now().utcoffset() == timedelta(0)


def test_new_id_shape() -> None:
    value = new_id()
    assert len(value) == 26
    assert is_ulid(value)


@pytest.mark.parametrize("value", ["nope", "", "U" * 26])
def test_is_ulid_rejects_invalid(value: str) -> None:
    assert not is_ulid(value)


def test_new_ids_sort_in_creation_order() -> None:
    ids = [new_id() for _ in range(1000)]
    assert ids == sorted(ids)


def test_both_clocks_satisfy_clock_protocol() -> None:
    at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert _read(FixedClock(at)) == at
    assert _read(SystemClock()).utcoffset() == timedelta(0)
