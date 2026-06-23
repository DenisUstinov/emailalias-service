from unittest.mock import AsyncMock, MagicMock

import pytest
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_async_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def integrity_error_unique_violation() -> IntegrityError:
    return IntegrityError(
        statement="INSERT/UPDATE ...",
        params=None,
        orig=UniqueViolation("duplicate key value violates unique constraint"),
    )
