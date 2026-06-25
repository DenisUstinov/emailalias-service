from unittest.mock import AsyncMock

import pytest

from app.repositories.verification import VerificationRepository
from app.schemas.verification import (
    VerificationActionType,
    VerificationSessionData,
    VerificationTokenData,
)


@pytest.mark.anyio
class TestVerificationRepository:
    async def test_increment_rate_limit_sets_expiration_on_first_call(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.incr.return_value = 1
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.increment_rate_limit("key", 60)

        assert result == 1
        redis_mock.incr.assert_awaited_once_with("key")
        redis_mock.expire.assert_awaited_once_with("key", 60)

    async def test_increment_rate_limit_does_not_set_expiration_on_subsequent_calls(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.incr.return_value = 2
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.increment_rate_limit("key", 60)

        assert result == 2
        redis_mock.incr.assert_awaited_once_with("key")
        redis_mock.expire.assert_not_awaited()

    async def test_get_session_id_by_email_hash(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = "session_123"
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_session_id_by_email_hash("hash_123")

        assert result == "session_123"
        redis_mock.get.assert_awaited_once_with("verification:email:hash_123")

    async def test_get_session_ttl(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.ttl.return_value = 3500
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_session_ttl("session_123")

        assert result == 3500
        redis_mock.ttl.assert_awaited_once_with("verification:session_123")

    async def test_get_session_returns_data_when_exists(self) -> None:
        redis_mock = AsyncMock()
        session_data = VerificationSessionData(
            email="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=0,
        )
        redis_mock.get.return_value = session_data.model_dump_json()
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_session("session_123")

        assert result == session_data
        redis_mock.get.assert_awaited_once_with("verification:session_123")

    async def test_get_session_returns_none_when_missing(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_session("unknown")

        assert result is None

    async def test_create_session_uses_pipeline(
        self, redis_with_pipeline: tuple[AsyncMock, AsyncMock]
    ) -> None:
        redis_mock, pipe_mock = redis_with_pipeline
        repo = VerificationRepository(redis=redis_mock)

        data = VerificationSessionData(
            email="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=0,
        )
        await repo.create_session("sess_id", "hash", data, 3600)

        pipe_mock.set.assert_any_await("verification:sess_id", data.model_dump_json(), ex=3600)
        pipe_mock.set.assert_any_await("verification:email:hash", "sess_id", ex=3600)
        pipe_mock.execute.assert_awaited_once()

    async def test_update_session_uses_pipeline_with_keepttl(
        self, redis_with_pipeline: tuple[AsyncMock, AsyncMock]
    ) -> None:
        redis_mock, pipe_mock = redis_with_pipeline
        repo = VerificationRepository(redis=redis_mock)

        data = VerificationSessionData(
            email="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=2,
            check_attempts=0,
        )
        await repo.update_session("sess_id", "hash", data)

        pipe_mock.set.assert_any_await("verification:sess_id", data.model_dump_json(), keepttl=True)
        pipe_mock.set.assert_any_await("verification:email:hash", "sess_id", keepttl=True)
        pipe_mock.execute.assert_awaited_once()

    async def test_delete_session_uses_pipeline(
        self, redis_with_pipeline: tuple[AsyncMock, AsyncMock]
    ) -> None:
        redis_mock, pipe_mock = redis_with_pipeline
        repo = VerificationRepository(redis=redis_mock)

        await repo.delete_session("sess_id", "hash")

        pipe_mock.delete.assert_any_await("verification:sess_id")
        pipe_mock.delete.assert_any_await("verification:email:hash")
        pipe_mock.execute.assert_awaited_once()

    async def test_save_token(self) -> None:
        redis_mock = AsyncMock()
        repo = VerificationRepository(redis=redis_mock)

        data = VerificationTokenData(
            email="test@example.com", action_type=VerificationActionType.USER_CREATION
        )
        await repo.save_token("token_hash", data, 3600)

        redis_mock.set.assert_awaited_once_with(
            "vtoken:token_hash", data.model_dump_json(), ex=3600
        )

    async def test_get_token_returns_data_when_exists(self) -> None:
        redis_mock = AsyncMock()
        token_data = VerificationTokenData(
            email="test@example.com", action_type=VerificationActionType.USER_CREATION
        )
        redis_mock.get.return_value = token_data.model_dump_json()
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_token("token_hash")

        assert result == token_data
        redis_mock.get.assert_awaited_once_with("vtoken:token_hash")

    async def test_get_token_returns_none_when_missing(self) -> None:
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        repo = VerificationRepository(redis=redis_mock)

        result = await repo.get_token("unknown")

        assert result is None

    async def test_delete_token(self) -> None:
        redis_mock = AsyncMock()
        repo = VerificationRepository(redis=redis_mock)

        await repo.delete_token("token_hash")

        redis_mock.delete.assert_awaited_once_with("vtoken:token_hash")
