from ulid import ULID


def new_id() -> str:
    return str(ULID())


def is_ulid(value: str) -> bool:
    try:
        ULID.from_str(value)
        return True
    except ValueError:
        return False
