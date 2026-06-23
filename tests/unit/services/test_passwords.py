from collections.abc import Callable
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import (
    EmailNotVerifiedError,
    UserBannedError,
    UserNotFoundError,
)
from app.models.domain import User
from app.schemas.requests import PasswordUpdateRequest
from app.services.passwords import PasswordService


@pytest.mark.anyio
class TestPasswordServiceUpdatePassword:
    async def test_success_updates_password(
        self,
        make_user: Callable[..., User],
        test_email: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        verification_service = AsyncMock()
        token_service = AsyncMock()

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            is_banned=False,
        )
        user_repo.get_by_email_for_update.return_value = user

        service = PasswordService(
            user_repo=user_repo,
            verification_service=verification_service,
            token_service=token_service,
        )

        request = PasswordUpdateRequest(
            email=test_email,
            new_password=new_valid_test_password,
            verification_token="a" * 43,
        )

        with patch("app.services.passwords.hash_password", return_value="$argon2id$new"):
            await service.update_password(request=request)

        verification_service.verify_operation_token.assert_awaited_once()
        user_repo.get_by_email_for_update.assert_awaited_once_with(test_email)
        user_repo.update.assert_awaited_once_with(
            user_id=user.id,
            password_hash="$argon2id$new",
        )
        token_service.revoke_active_tokens.assert_awaited_once_with(user.id)

    async def test_raises_when_email_not_verified(
        self,
        test_email: str,
        new_valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        verification_service = AsyncMock()
        verification_service.verify_operation_token.side_effect = EmailNotVerifiedError()

        service = PasswordService(
            user_repo=user_repo,
            verification_service=verification_service,
            token_service=AsyncMock(),
        )

        request = PasswordUpdateRequest(
            email=test_email,
            new_password=new_valid_test_password,
            verification_token="a" * 43,
        )

        with pytest.raises(EmailNotVerifiedError) as exc_info:
            await service.update_password(request=request)

        assert exc_info.value.status_code == 400
        user_repo.get_by_email_for_update.assert_not_awaited()

    async def test_raises_when_user_not_found(
        self,
        test_email: str,
        new_valid_test_password: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        verification_service = AsyncMock()
        user_repo.get_by_email_for_update.return_value = None

        service = PasswordService(
            user_repo=user_repo,
            verification_service=verification_service,
            token_service=AsyncMock(),
        )

        request = PasswordUpdateRequest(
            email=test_email,
            new_password=new_valid_test_password,
            verification_token="a" * 43,
        )

        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_password(request=request)

        assert exc_info.value.status_code == 404

    async def test_raises_when_user_banned(
        self,
        make_user: Callable[..., User],
        test_email: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        verification_service = AsyncMock()

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            is_banned=True,
        )
        user_repo.get_by_email_for_update.return_value = user

        service = PasswordService(
            user_repo=user_repo,
            verification_service=verification_service,
            token_service=AsyncMock(),
        )

        request = PasswordUpdateRequest(
            email=test_email,
            new_password=new_valid_test_password,
            verification_token="a" * 43,
        )

        with pytest.raises(UserBannedError) as exc_info:
            await service.update_password(request=request)

        assert exc_info.value.status_code == 403
        user_repo.update.assert_not_awaited()

    async def test_success_handles_token_revocation_failure(
        self,
        make_user: Callable[..., User],
        test_email: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo = mock_async_repository
        verification_service = AsyncMock()
        token_service = AsyncMock()
        token_service.revoke_active_tokens.side_effect = Exception("Redis down")

        user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            is_banned=False,
        )
        user_repo.get_by_email_for_update.return_value = user

        service = PasswordService(
            user_repo=user_repo,
            verification_service=verification_service,
            token_service=token_service,
        )

        request = PasswordUpdateRequest(
            email=test_email,
            new_password=new_valid_test_password,
            verification_token="a" * 43,
        )

        with patch("app.services.passwords.hash_password", return_value="$argon2id$new"):
            await service.update_password(request=request)

        user_repo.update.assert_awaited_once()
