"""ULID identifiers for traces, tool calls, actions and rows."""

from ulid import ULID


def new_id() -> str:
    return str(ULID())


def is_ulid(value: str) -> bool:
    try:
        ULID.from_str(value)
    except ValueError:
        return False
    return True
