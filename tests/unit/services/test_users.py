from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    CurrentPasswordInvalidError,
    CurrentPasswordRequiredError,
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    UserBannedError,
    UserNotFoundError,
)
from app.models.domain import User, UserRole
from app.schemas.requests import UserCreateRequest
from app.schemas.responses import UserAdminUpdateResponse, UserCreateResponse, UserUpdateResponse
from app.services.users import UserService


@pytest.mark.anyio
class TestUserServiceCreateUser:
    async def test_success_creates_new_user(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        token_service_mock = AsyncMock()

        created_user = make_user(
            user_id=test_uuids["user_1"],
            email=test_email,
            password_hash="$argon2id$hashed",
        )
        user_repo_mock.get_by_email_including_deleted_for_update.return_value = None
        user_repo_mock.create.return_value = created_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=token_service_mock,
        )

        request = UserCreateRequest(
            email=test_email, password=valid_test_password, verification_token="a" * 43
        )

        with patch("app.services.users.hash_password", return_value="$argon2id$hashed"):
            result = await service.create_user(request)

        verification_service_mock.verify_operation_token.assert_awaited_once()
        user_repo_mock.create.assert_awaited_once()
        assert isinstance(result, UserCreateResponse)
        assert result.email == test_email

    async def test_success_reactivates_deleted_user(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        token_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email)
        existing_user.deleted_at = datetime(2023, 1, 1, tzinfo=UTC)

        user_repo_mock.get_by_email_including_deleted_for_update.return_value = existing_user
        user_repo_mock.reactivate.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=token_service_mock,
        )

        request = UserCreateRequest(
            email=test_email, password=valid_test_password, verification_token="a" * 43
        )

        with patch("app.services.users.hash_password", return_value="$argon2id$hashed"):
            result = await service.create_user(request)

        user_repo_mock.reactivate.assert_awaited_once()
        assert isinstance(result, UserCreateResponse)

    async def test_raises_when_email_not_verified(
        self,
        valid_test_password: str,
        test_email: str,
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        verification_service_mock.verify_operation_token.side_effect = EmailNotVerifiedError()

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        request = UserCreateRequest(
            email=test_email, password=valid_test_password, verification_token="a" * 43
        )

        with pytest.raises(EmailNotVerifiedError) as exc_info:
            await service.create_user(request)

        assert exc_info.value.status_code == 400

    async def test_raises_when_user_banned(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email, is_banned=True)
        existing_user.deleted_at = None
        user_repo_mock.get_by_email_including_deleted_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        request = UserCreateRequest(
            email=test_email, password=valid_test_password, verification_token="a" * 43
        )

        with pytest.raises(UserBannedError) as exc_info:
            await service.create_user(request)

        assert exc_info.value.status_code == 403

    async def test_raises_when_email_already_exists(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email, is_banned=False)
        existing_user.deleted_at = None
        user_repo_mock.get_by_email_including_deleted_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        request = UserCreateRequest(
            email=test_email, password=valid_test_password, verification_token="a" * 43
        )

        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            await service.create_user(request)

        assert exc_info.value.status_code == 409


@pytest.mark.anyio
class TestUserServiceDeleteUser:
    async def test_success_deletes_user(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        token_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email)
        existing_user.is_banned = False
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=token_service_mock,
        )

        await service.delete_user(user_id=existing_user.id, verification_token="a" * 43)

        user_repo_mock.get_by_id_for_update.assert_awaited_once_with(existing_user.id)
        verification_service_mock.verify_operation_token.assert_awaited_once()
        user_repo_mock.delete.assert_awaited_once_with(existing_user.id)
        token_service_mock.revoke_active_tokens.assert_awaited_once_with(existing_user.id)

    async def test_returns_none_when_user_not_found(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        user_repo_mock.get_by_id_for_update.return_value = None

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        result = await service.delete_user(
            user_id=test_uuids["user_3"], verification_token="a" * 43
        )
        assert result is None

    async def test_raises_when_user_banned(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email)
        existing_user.is_banned = True
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with pytest.raises(UserBannedError) as exc_info:
            await service.delete_user(user_id=existing_user.id, verification_token="a" * 43)

        assert exc_info.value.status_code == 403

    async def test_raises_when_email_not_verified(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        verification_service_mock.verify_operation_token.side_effect = EmailNotVerifiedError()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email)
        existing_user.is_banned = False
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        with pytest.raises(EmailNotVerifiedError) as exc_info:
            await service.delete_user(user_id=existing_user.id, verification_token="a" * 43)

        assert exc_info.value.status_code == 400

    async def test_success_handles_token_revocation_failure(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        token_service_mock = AsyncMock()
        token_service_mock.revoke_active_tokens.side_effect = Exception("Redis down")

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email)
        existing_user.is_banned = False
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=token_service_mock,
        )

        await service.delete_user(user_id=existing_user.id, verification_token="a" * 43)

        user_repo_mock.delete.assert_awaited_once()


@pytest.mark.anyio
class TestUserServiceUpdateUser:
    async def test_success_update_email(
        self,
        make_user: Callable[..., User],
        test_email_alt: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        token_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email="old@example.com")
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        updated_user = make_user(user_id=test_uuids["user_1"], email=test_email_alt)
        user_repo_mock.update.return_value = updated_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=token_service_mock,
        )

        result = await service.update_user(
            user_id=existing_user.id,
            email=test_email_alt,
            verification_token="a" * 43,
        )

        assert isinstance(result, UserUpdateResponse)
        assert result.email == test_email_alt
        verification_service_mock.verify_operation_token.assert_awaited_once()
        token_service_mock.revoke_active_tokens.assert_awaited_once()

    async def test_success_update_password(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        token_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], password_hash="$argon2id$old")
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        updated_user = make_user(user_id=test_uuids["user_1"], password_hash="$argon2id$new")
        user_repo_mock.update.return_value = updated_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=token_service_mock,
        )

        with (
            patch("app.services.users.verify_password", return_value=True),
            patch("app.services.users.hash_password", return_value="$argon2id$new"),
        ):
            result = await service.update_user(
                user_id=existing_user.id,
                new_password=new_valid_test_password,
                current_password=valid_test_password,
            )

        assert isinstance(result, UserUpdateResponse)
        token_service_mock.revoke_active_tokens.assert_awaited_once()

    async def test_raises_when_password_change_without_current_password(
        self,
        make_user: Callable[..., User],
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        existing_user = make_user(user_id=test_uuids["user_1"])
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with pytest.raises(CurrentPasswordRequiredError) as exc_info:
            await service.update_user(
                user_id=existing_user.id,
                new_password=new_valid_test_password,
                current_password=None,
            )

        assert exc_info.value.status_code == 400

    async def test_raises_when_user_not_found_for_password_update(
        self,
        valid_test_password: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        user_repo_mock.get_by_id_for_update.return_value = None

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_user(
                user_id=test_uuids["user_3"],
                new_password=new_valid_test_password,
                current_password=valid_test_password,
            )

        assert exc_info.value.status_code == 404

    async def test_raises_when_current_password_invalid(
        self,
        make_user: Callable[..., User],
        valid_test_password: str,
        new_valid_test_password: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        existing_user = make_user(user_id=test_uuids["user_1"])
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with (
            patch("app.services.users.verify_password", return_value=False),
            pytest.raises(CurrentPasswordInvalidError) as exc_info,
        ):
            await service.update_user(
                user_id=existing_user.id,
                new_password=new_valid_test_password,
                current_password=valid_test_password,
            )

        assert exc_info.value.status_code == 400

    async def test_raises_when_email_update_without_verification_token(
        self,
        make_user: Callable[..., User],
        test_email_alt: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        existing_user = make_user(user_id=test_uuids["user_1"])
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with pytest.raises(CurrentPasswordRequiredError) as exc_info:
            await service.update_user(
                user_id=existing_user.id,
                email=test_email_alt,
                verification_token=None,
            )

        assert exc_info.value.status_code == 400

    async def test_raises_when_email_not_verified(
        self,
        make_user: Callable[..., User],
        test_email_alt: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()
        verification_service_mock.verify_operation_token.side_effect = EmailNotVerifiedError()

        existing_user = make_user(user_id=test_uuids["user_1"])
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        with pytest.raises(EmailNotVerifiedError) as exc_info:
            await service.update_user(
                user_id=existing_user.id,
                email=test_email_alt,
                verification_token="a" * 43,
            )

        assert exc_info.value.status_code == 400

    async def test_raises_when_email_already_exists_on_update(
        self,
        make_user: Callable[..., User],
        test_email_alt: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
        integrity_error_unique_violation: IntegrityError,
    ) -> None:
        user_repo_mock = mock_async_repository
        verification_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"])
        user_repo_mock.get_by_id_for_update.return_value = existing_user
        user_repo_mock.update.side_effect = integrity_error_unique_violation

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=verification_service_mock,
            token_service=AsyncMock(),
        )

        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            await service.update_user(
                user_id=existing_user.id,
                email=test_email_alt,
                verification_token="a" * 43,
            )

        assert exc_info.value.status_code == 409


@pytest.mark.anyio
class TestUserServiceUpdateUserAdmin:
    async def test_success_update_ban_status(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        token_service_mock = AsyncMock()

        existing_user = make_user(user_id=test_uuids["user_1"], email=test_email, is_banned=False)
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        updated_user = make_user(user_id=test_uuids["user_1"], email=test_email, is_banned=True)
        user_repo_mock.update.return_value = updated_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=token_service_mock,
        )

        result = await service.update_user_admin(
            user_id=existing_user.id,
            is_banned=True,
        )

        assert isinstance(result, UserAdminUpdateResponse)
        assert result.is_banned is True
        token_service_mock.revoke_active_tokens.assert_awaited_once()

    async def test_success_update_role(
        self,
        make_user: Callable[..., User],
        test_email: str,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        token_service_mock = AsyncMock()

        existing_user = make_user(
            user_id=test_uuids["user_1"], email=test_email, role=UserRole.USER
        )
        user_repo_mock.get_by_id_for_update.return_value = existing_user

        updated_user = make_user(
            user_id=test_uuids["user_1"], email=test_email, role=UserRole.ADMIN
        )
        user_repo_mock.update.return_value = updated_user

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=token_service_mock,
        )

        result = await service.update_user_admin(
            user_id=existing_user.id,
            role=UserRole.ADMIN,
        )

        assert isinstance(result, UserAdminUpdateResponse)
        assert result.role == UserRole.ADMIN.value

    async def test_raises_when_user_not_found(
        self,
        test_uuids: dict[str, UUID],
        mock_async_repository: AsyncMock,
    ) -> None:
        user_repo_mock = mock_async_repository
        user_repo_mock.get_by_id_for_update.return_value = None

        service = UserService(
            user_repo=user_repo_mock,
            verification_service=AsyncMock(),
            token_service=AsyncMock(),
        )

        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_user_admin(
                user_id=test_uuids["user_3"],
                is_banned=True,
            )

        assert exc_info.value.status_code == 404
