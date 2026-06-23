from collections.abc import Callable
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import InvalidCredentialsError, UserBannedError
from app.models.domain import User
from app.schemas.responses import TokenCreateResponse
from app.services.tokens import TokenService


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
        user_repo.get_by_email.return_value = user
        token_repo.get_hashed_token_by_user_id.return_value = None

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
        user_repo.get_by_email.assert_awaited_once_with(test_email)
        token_repo.get_hashed_token_by_user_id.assert_awaited_once_with(user.id)
        token_repo.create.assert_awaited_once()
        call_args = token_repo.create.call_args[0]
        assert call_args[0] == "hashed_token"
        assert call_args[1].user_id == user.id
        assert call_args[1].role == user.role

    async def test_raises_invalid_credentials_when_user_not_found(
        self,
        valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        token_repo = AsyncMock()

        user_repo.get_by_email.return_value = None

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

        with pytest.raises(InvalidCredentialsError) as exc_info:
            await service.create_token(
                email="unknown@example.com",
                password=valid_test_password,
            )

        assert exc_info.value.status_code == 401
        user_repo.get_by_email.assert_awaited_once_with("unknown@example.com")
        token_repo.get_hashed_token_by_user_id.assert_not_awaited()

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
        user_repo.get_by_email.return_value = user

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

        with (
            patch("app.services.tokens.verify_password", return_value=False),
            pytest.raises(InvalidCredentialsError) as exc_info,
        ):
            await service.create_token(
                email=test_email,
                password=invalid_test_password,
            )

        assert exc_info.value.status_code == 401
        user_repo.get_by_email.assert_awaited_once_with(test_email)
        token_repo.get_hashed_token_by_user_id.assert_not_awaited()

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
        user_repo.get_by_email.return_value = user
        token_repo.get_hashed_token_by_user_id.return_value = None

        service = TokenService(user_repo=user_repo, token_repo=token_repo)

        with (
            patch("app.services.tokens.verify_password", return_value=True),
            pytest.raises(UserBannedError) as exc_info,
        ):
            await service.create_token(
                email=test_email,
                password=valid_test_password,
            )

        assert exc_info.value.status_code == 403
        user_repo.get_by_email.assert_awaited_once_with(test_email)
        token_repo.get_hashed_token_by_user_id.assert_awaited_once_with(user.id)

    async def test_revokes_previous_token_when_exists(
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
        user_repo.get_by_email.return_value = user
        token_repo.get_hashed_token_by_user_id.return_value = "old_hashed_token"

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
        token_repo.get_hashed_token_by_user_id.assert_awaited_once_with(user.id)
        token_repo.delete.assert_awaited_once_with("old_hashed_token")
        token_repo.create.assert_awaited_once()
