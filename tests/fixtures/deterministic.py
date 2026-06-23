from datetime import UTC, datetime
from uuid import UUID

import pytest


@pytest.fixture
def test_uuids() -> dict[str, UUID]:
    return {
        "user_1": UUID("00000000-0000-0000-0000-000000000001"),
        "user_2": UUID("00000000-0000-0000-0000-000000000002"),
        "user_3": UUID("00000000-0000-0000-0000-000000000003"),
    }


@pytest.fixture
def frozen_utc_time() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
