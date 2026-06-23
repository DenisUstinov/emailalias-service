from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.repositories.tokens import TokenRepository
from app.schemas.token import TokenData


@pytest.mark.anyio
class TestTokenRepository:
    async def test_create_sets_expiration(self, test_uuids: dict[str, UUID]) -> None:
        redis_mock = AsyncMock()
        pipe_mock = AsyncMock()
        redis_mock.pipeline = Mock(return_value=pipe_mock)

        repo = TokenRepository(redis=redis_mock)
        hashed_token = "abc123"
        data = TokenData(user_id=test_uuids["user_1"], role="user")
        expire_seconds = 900

        await repo.create(hashed_token, data, expire_seconds)

        pipe_mock.set.assert_any_call(
            f"tkn:{hashed_token}", data.model_dump_json(), ex=expire_seconds
        )
        pipe_mock.set.assert_any_call(f"usr:{data.user_id}", hashed_token, ex=expire_seconds)
        pipe_mock.execute.assert_awaited_once()

    async def test_get_returns_token_data_when_exists(self, test_uuids: dict[str, UUID]) -> None:
        redis_mock = AsyncMock()
        session_data = TokenData(user_id=test_uuids["user_1"], role="admin")
        redis_mock.get.return_value = session_data.model_dump_json()

        repo = TokenRepository(redis=redis_mock)
        result = await repo.get("abc123")

        assert result == session_data
        redis_mock.get.assert_awaited_once_with("tkn:abc123")

    async def test_get_returns_none_when_missing(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        repo = TokenRepository(redis=redis_mock)
        result = await repo.get("unknown")

        assert result is None
        redis_mock.get.assert_awaited_once_with("tkn:unknown")

    async def test_delete_removes_both_keys(self, test_uuids: dict[str, UUID]) -> None:
        redis_mock = AsyncMock()
        pipe_mock = AsyncMock()
        redis_mock.pipeline = Mock(return_value=pipe_mock)

        session_data = TokenData(user_id=test_uuids["user_1"], role="user")
        redis_mock.get.return_value = session_data.model_dump_json()

        repo = TokenRepository(redis=redis_mock)
        await repo.delete("abc123")

        pipe_mock.delete.assert_any_call("tkn:abc123")
        pipe_mock.delete.assert_any_call(f"usr:{session_data.user_id}")
        pipe_mock.execute.assert_awaited_once()

    async def test_delete_does_nothing_when_token_missing(self) -> None:
        redis_mock = AsyncMock()
        pipe_mock = AsyncMock()
        redis_mock.pipeline = Mock(return_value=pipe_mock)
        redis_mock.get.return_value = None

        repo = TokenRepository(redis=redis_mock)
        await repo.delete("unknown")

        redis_mock.get.assert_awaited_once_with("tkn:unknown")
        pipe_mock.delete.assert_not_called()
        pipe_mock.execute.assert_not_called()

    async def test_get_hashed_token_by_user_id(self, test_uuids: dict[str, UUID]) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = "abc123"

        repo = TokenRepository(redis=redis_mock)
        result = await repo.get_hashed_token_by_user_id(test_uuids["user_1"])

        assert result == "abc123"
        redis_mock.get.assert_awaited_once_with(f"usr:{test_uuids['user_1']}")

    async def test_get_hashed_token_by_user_id_returns_none(
        self, test_uuids: dict[str, UUID]
    ) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        repo = TokenRepository(redis=redis_mock)
        result = await repo.get_hashed_token_by_user_id(test_uuids["user_1"])

        assert result is None
        redis_mock.get.assert_awaited_once_with(f"usr:{test_uuids['user_1']}")
