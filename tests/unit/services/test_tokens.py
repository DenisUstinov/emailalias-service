from collections.abc import Callable
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import InvalidCredentialsError, UserBannedError
from app.models.domain import User
from app.schemas.responses import TokenCreateResponse
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

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
        )
        user_repo.get_by_email_for_update.return_value = user
        token_repo.revoke_all_by_user_id.return_value = 0

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

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

    async def test_raises_invalid_credentials_when_user_not_found(
        self,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()

        user_repo.get_by_email_for_update.return_value = None

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

        with pytest.raises(InvalidCredentialsError) as exc_info:
            await service.create_token(
                email="unknown@example.com",
                password=valid_test_password,
            )

        assert_exception_details(exc_info, 401, InvalidCredentialsError)
        user_repo.get_by_email_for_update.assert_awaited_once_with("unknown@example.com")
        token_repo.revoke_all_by_user_id.assert_not_awaited()

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

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$correct_hash",
        )
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

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

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
            is_banned=True,
        )
        user_repo.get_by_email_for_update.return_value = user

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

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

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
        )
        user_repo.get_by_email_for_update.return_value = user
        token_repo.revoke_all_by_user_id.return_value = 1

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

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
