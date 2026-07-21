from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import (
    InvalidCredentialsError,
    TokenPasswordAttemptsBlockedError,
    UserBannedError,
)
from app.models.domain import User
from app.schemas.responses import TokenCreateResponse
from app.schemas.tokens import PasswordAttemptSessionData
from app.services.tokens import TokenService
from tests.helpers import assert_exception_details


@pytest.mark.anyio
class TestTokenServiceCreateToken:
    async def test_success_creates_token(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()
        password_attempt_repo.get_session.return_value = None

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
        )
        user_repo.get_by_email_for_update.return_value = user
        token_repo.revoke_all_by_user_id.return_value = 0

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=True),
            patch("app.services.tokens.secrets.token_urlsafe", return_value="raw_token"),
            patch("app.services.tokens.hash_token", return_value="hashed_token"),
        ):
            result = await service.create_token(
                email=test_email,
                password=valid_test_password,
            )

        assert isinstance(result, TokenCreateResponse)
        assert result.access_token == "raw_token"
        user_repo.get_by_email_for_update.assert_awaited_once_with(test_email)
        token_repo.revoke_all_by_user_id.assert_awaited_once_with(user.id)
        token_repo.create.assert_awaited_once_with(hashed_token="hashed_token", user_id=user.id)
        password_attempt_repo.delete_session.assert_awaited_once()

    async def test_raises_invalid_credentials_when_user_not_found(
        self,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
        generate_test_email,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()
        password_attempt_repo.get_session.return_value = None

        user_repo.get_by_email_for_update.return_value = None
        unknown_email = generate_test_email(prefix="unknown")

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with pytest.raises(InvalidCredentialsError) as exc_info:
            await service.create_token(
                email=unknown_email,
                password=valid_test_password,
            )

        assert_exception_details(exc_info, 401, InvalidCredentialsError)
        user_repo.get_by_email_for_update.assert_awaited_once_with(unknown_email)
        token_repo.revoke_all_by_user_id.assert_not_awaited()
        password_attempt_repo.get_session.assert_awaited_once()
        password_attempt_repo.save_session.assert_not_awaited()

    async def test_raises_invalid_credentials_when_password_wrong(
        self,
        make_user: Callable[..., User],
        test_email: str,
        valid_test_password: str,
        invalid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()
        password_attempt_repo.get_session.return_value = None

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$correct_hash",
        )
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError) as exc_info,
        ):
            await service.create_token(
                email=test_email,
                password=invalid_test_password,
            )

        assert_exception_details(exc_info, 401, InvalidCredentialsError)
        user_repo.get_by_email_for_update.assert_awaited_once_with(test_email)
        token_repo.revoke_all_by_user_id.assert_not_awaited()
        password_attempt_repo.save_session.assert_awaited_once()

    async def test_raises_user_banned_when_user_banned(
        self,
        make_user: Callable[..., User],
        test_email: str,
        valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()
        password_attempt_repo.get_session.return_value = None

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
            is_banned=True,
        )
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=True),
            pytest.raises(UserBannedError) as exc_info,
        ):
            await service.create_token(
                email=test_email,
                password=valid_test_password,
            )

        assert_exception_details(exc_info, 403, UserBannedError)
        user_repo.get_by_email_for_update.assert_awaited_once_with(test_email)
        token_repo.revoke_all_by_user_id.assert_not_awaited()

    async def test_revokes_active_tokens_on_login(
        self,
        make_user: Callable[..., User],
        test_email: str,
        valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()
        password_attempt_repo.get_session.return_value = None

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
        )
        user_repo.get_by_email_for_update.return_value = user
        token_repo.revoke_all_by_user_id.return_value = 1

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=True),
            patch("app.services.tokens.secrets.token_urlsafe", return_value="new_raw_token"),
            patch("app.services.tokens.hash_token", return_value="new_hashed_token"),
        ):
            result = await service.create_token(
                email=test_email,
                password=valid_test_password,
            )

        assert isinstance(result, TokenCreateResponse)
        assert result.access_token == "new_raw_token"
        token_repo.revoke_all_by_user_id.assert_awaited_once_with(user.id)
        token_repo.create.assert_awaited_once_with(hashed_token="new_hashed_token", user_id=user.id)
        password_attempt_repo.delete_session.assert_awaited_once()

    async def test_raises_blocked_when_session_active_and_blocked(
        self,
        test_email: str,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()

        now = datetime.now(UTC)
        blocked_until = now + timedelta(minutes=10)
        session = PasswordAttemptSessionData(
            failed_attempts=3,
            window_start=now,
            blocked_until=blocked_until,
            last_block_ts=now,
        )
        password_attempt_repo.get_session.return_value = session

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with pytest.raises(TokenPasswordAttemptsBlockedError) as exc_info:
            await service.create_token(
                email=test_email,
                password=valid_test_password,
            )

        assert exc_info.value.status_code == 423
        assert "Try again in" in exc_info.value.detail
        user_repo.get_by_email_for_update.assert_not_awaited()
        token_repo.revoke_all_by_user_id.assert_not_awaited()

    async def test_handle_failed_attempt_increments_counter_and_applies_block(
        self,
        test_email: str,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()

        user = mock_async_repository.return_value
        user.password_hash = "$argon2id$hash"
        user_repo.get_by_email_for_update.return_value = user
        password_attempt_repo.get_session.return_value = None

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError),
        ):
            await service.create_token(email=test_email, password=valid_test_password)

        saved_session = password_attempt_repo.save_session.call_args[0][1]
        assert isinstance(saved_session, PasswordAttemptSessionData)
        assert saved_session.failed_attempts == 1
        assert saved_session.blocked_until is None

    async def test_handle_failed_attempt_triggers_15min_block_on_third_failure(
        self,
        test_email: str,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()

        now = datetime.now(UTC)
        existing_session = PasswordAttemptSessionData(
            failed_attempts=2,
            window_start=now,
            blocked_until=None,
            last_block_ts=None,
        )
        password_attempt_repo.get_session.return_value = existing_session

        user = mock_async_repository.return_value
        user.password_hash = "$argon2id$hash"
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError),
        ):
            await service.create_token(email=test_email, password=valid_test_password)

        saved_session = password_attempt_repo.save_session.call_args[0][1]
        assert saved_session.failed_attempts == 3
        assert saved_session.blocked_until is not None
        assert saved_session.blocked_until >= now + timedelta(minutes=15)
        assert saved_session.last_block_ts is not None

    async def test_handle_failed_attempt_triggers_1h_block_on_repeated_failure_within_hour(
        self,
        test_email: str,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        user_repo = mock_async_repository
        token_repo = AsyncMock()
        password_attempt_repo = AsyncMock()

        now = datetime.now(UTC)
        existing_session = PasswordAttemptSessionData(
            failed_attempts=2,
            window_start=now,
            blocked_until=None,
            last_block_ts=now - timedelta(minutes=30),
        )
        password_attempt_repo.get_session.return_value = existing_session

        user = mock_async_repository.return_value
        user.password_hash = "$argon2id$hash"
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(
            user_repo=user_repo,
            token_repo=token_repo,
            password_attempt_repo=password_attempt_repo,
        )

        with (
            patch("app.services.tokens.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError),
        ):
            await service.create_token(email=test_email, password=valid_test_password)

        saved_session = password_attempt_repo.save_session.call_args[0][1]
        assert saved_session.failed_attempts == 3
        assert saved_session.blocked_until is not None
        assert saved_session.blocked_until >= now + timedelta(hours=1)
        assert saved_session.last_block_ts is not None
        assert saved_session.last_block_ts >= now
        assert (saved_session.last_block_ts - now).total_seconds() < 1
