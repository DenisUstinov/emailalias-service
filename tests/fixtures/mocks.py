from unittest.mock import AsyncMock, MagicMock, Mock

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
def redis_with_pipeline() -> tuple[AsyncMock, AsyncMock]:
    redis_mock = AsyncMock()
    pipe_mock = AsyncMock()
    redis_mock.pipeline = Mock(return_value=pipe_mock)
    return redis_mock, pipe_mock


@pytest.fixture
def integrity_error_unique_violation() -> IntegrityError:
    return IntegrityError(
        statement="INSERT/UPDATE ...",
        params=None,
        orig=UniqueViolation("duplicate key value violates unique constraint"),
    )
