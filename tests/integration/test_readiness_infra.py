import pytest

from marketmind.api.readiness import check_postgres, check_redis
from marketmind.core.config import Settings

pytestmark = pytest.mark.integration


async def test_postgres_is_reachable_and_has_pgvector() -> None:
    await check_postgres(Settings().database_url, require_extension="vector")


async def test_redis_is_reachable() -> None:
    await check_redis(Settings().redis_url)
