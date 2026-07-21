import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, NoResultFound

from app.core.exceptions import (
    CurrentPasswordInvalidError,
    CurrentPasswordRequiredError,
    EmailAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
)
from app.models.domain import User, UserRole
from app.schemas.requests import UserCreateRequest
from app.schemas.verification import VerificationActionType
from app.services.users import UserService
from tests.helpers import assert_exception_details


def _make_service(**overrides: object) -> UserService:
    defaults = {
        "user_repo": AsyncMock(),
        "verification_service": AsyncMock(),
        "token_repo": AsyncMock(),
    }
    defaults.update(overrides)
    return UserService(**defaults)


@pytest.mark.anyio
class TestUserServiceCreateUser:
    async def test_success_creates_new_user(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user_repo.get_by_email_including_deleted_for_update.return_value = None
        created_user = User(
            id=uuid.uuid4(),
            email=test_email,
            password_hash="hashed",
            created_at=datetime.now(UTC),
        )
        user_repo.create.return_value = created_user
        verification_service = AsyncMock()
        service = _make_service(user_repo=user_repo, verification_service=verification_service)
        request = UserCreateRequest(
            email=test_email,
            password="ValidP@ss123",
            verification_token="V" * 43,
        )
        with patch("app.services.users.hash_password", return_value="hashed"):
            result = await service.create_user(request)
            assert result.email == test_email
            verification_service.verify_operation_token.assert_awaited_once_with(
                token="V" * 43,
                contact=test_email,
                expected_action=VerificationActionType.USER_CREATION,
            )
            user_repo.create.assert_awaited_once()

    async def test_success_reactivates_deleted_user(self, test_email: str) -> None:
        user_repo = AsyncMock()
        deleted_user = User(
            id=uuid.uuid4(),
            email=test_email,
            password_hash="old_hash",
            deleted_at=MagicMock(),
            created_at=datetime.now(UTC),
        )
        user_repo.get_by_email_including_deleted_for_update.return_value = deleted_user
        user_repo.reactivate.return_value = deleted_user
        service = _make_service(user_repo=user_repo)
        request = UserCreateRequest(
            email=test_email,
            password="ValidP@ss123",
            verification_token="V" * 43,
        )
        with patch("app.services.users.hash_password", return_value="new_hash"):
            await service.create_user(request)
            user_repo.reactivate.assert_awaited_once()

    async def test_raises_user_banned_if_existing_user_is_banned(self, test_email: str) -> None:
        user_repo = AsyncMock()
        banned_user = User(
            id=uuid.uuid4(),
            email=test_email,
            is_banned=True,
            deleted_at=None,
        )
        user_repo.get_by_email_including_deleted_for_update.return_value = banned_user
        service = _make_service(user_repo=user_repo)
        request = UserCreateRequest(
            email=test_email,
            password="ValidP@ss123",
            verification_token="V" * 43,
        )
        with pytest.raises(UserBannedError) as exc_info:
            await service.create_user(request)
        assert_exception_details(exc_info, 403, UserBannedError)

    async def test_raises_email_already_exists_if_active_user_exists(self, test_email: str) -> None:
        user_repo = AsyncMock()
        active_user = User(id=uuid.uuid4(), email=test_email, deleted_at=None)
        user_repo.get_by_email_including_deleted_for_update.return_value = active_user
        service = _make_service(user_repo=user_repo)
        request = UserCreateRequest(
            email=test_email,
            password="ValidP@ss123",
            verification_token="V" * 43,
        )
        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            await service.create_user(request)
        assert_exception_details(exc_info, 409, EmailAlreadyExistsError)


@pytest.mark.anyio
class TestUserServiceDeleteUser:
    async def test_success_deletes_user_and_revokes_tokens(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email)
        user_repo.get_by_id_for_update.return_value = user
        token_repo = AsyncMock()
        verification_service = AsyncMock()
        service = _make_service(
            user_repo=user_repo,
            token_repo=token_repo,
            verification_service=verification_service,
        )
        await service.delete_user(user.id, "V" * 43)
        user_repo.delete.assert_awaited_once_with(user.id)
        verification_service.verify_operation_token.assert_awaited_once_with(
            token="V" * 43,
            contact=test_email,
            expected_action=VerificationActionType.USER_DELETION,
        )
        token_repo.revoke_all_by_user_id.assert_awaited_once_with(user.id)

    async def test_revokes_tokens_if_user_not_found(self) -> None:
        user_repo = AsyncMock()
        user_repo.get_by_id_for_update.return_value = None
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        await service.delete_user(uuid.uuid4(), "V" * 43)
        token_repo.revoke_all_by_user_id.assert_awaited_once()

    async def test_raises_user_banned_on_delete(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, is_banned=True)
        user_repo.get_by_id_for_update.return_value = user
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        with pytest.raises(UserBannedError) as exc_info:
            await service.delete_user(user.id, "V" * 43)
        assert_exception_details(exc_info, 403, UserBannedError)
        token_repo.revoke_all_by_user_id.assert_awaited_once_with(user.id)


@pytest.mark.anyio
class TestUserServiceUpdateUser:
    async def test_raises_user_not_found(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user_repo.get_by_id_for_update.return_value = None
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_user(
                user_id=uuid.uuid4(),
                new_password="NewP@ss123",
                current_password="OldP@ss123",
            )
        assert_exception_details(exc_info, 404, UserNotFoundError)
        token_repo.revoke_all_by_user_id.assert_awaited_once()

    async def test_raises_user_banned(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, is_banned=True)
        user_repo.get_by_id_for_update.return_value = user
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        with pytest.raises(UserBannedError) as exc_info:
            await service.update_user(user_id=user.id)
        assert_exception_details(exc_info, 403, UserBannedError)
        token_repo.revoke_all_by_user_id.assert_awaited_once()

    async def test_raises_current_password_required(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, password_hash="hash")
        user_repo.get_by_id_for_update.return_value = user
        service = _make_service(user_repo=user_repo)
        with pytest.raises(CurrentPasswordRequiredError) as exc_info:
            await service.update_user(user_id=user.id, new_password="NewP@ss123")
        assert_exception_details(exc_info, 400, CurrentPasswordRequiredError)

    async def test_raises_current_password_invalid(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, password_hash="hash")
        user_repo.get_by_id_for_update.return_value = user
        service = _make_service(user_repo=user_repo)
        with (
            patch("app.services.users.verify_password", return_value=False),
            pytest.raises(CurrentPasswordInvalidError) as exc_info,
        ):
            await service.update_user(
                user_id=user.id,
                new_password="NewP@ss123",
                current_password="WrongP@ss",
            )
        assert_exception_details(exc_info, 400, CurrentPasswordInvalidError)

    async def test_raises_email_already_exists_on_integrity_error(
        self, test_email: str, test_email_alt: str
    ) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, password_hash="hash")
        user_repo.get_by_id_for_update.return_value = user
        user_repo.update.side_effect = IntegrityError("stmt", {}, Exception())
        service = _make_service(user_repo=user_repo)
        with (
            patch("app.services.users.verify_password", return_value=True),
            pytest.raises(EmailAlreadyExistsError) as exc_info,
        ):
            await service.update_user(
                user_id=user.id,
                email=test_email_alt,
                new_password="NewP@ss123",
                current_password="OldP@ss",
            )
        assert_exception_details(exc_info, 409, EmailAlreadyExistsError)

    async def test_success_updates_password(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, password_hash="old_hash")
        user_repo.get_by_id_for_update.return_value = user
        updated_user = User(
            id=user.id,
            email=user.email,
            password_hash="new_hash",
            updated_at=datetime.now(UTC),
        )
        user_repo.update.return_value = updated_user
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        with (
            patch("app.services.users.verify_password", return_value=True),
            patch("app.services.users.hash_password", return_value="new_hash"),
        ):
            result = await service.update_user(
                user_id=user.id,
                new_password="NewP@ss123",
                current_password="OldP@ss",
            )
            assert result.email == updated_user.email
            assert result.updated_at == updated_user.updated_at
            user_repo.update.assert_awaited_once_with(
                user_id=user.id, email=None, password_hash="new_hash"
            )
            token_repo.revoke_all_by_user_id.assert_awaited_once_with(user.id)

    async def test_success_updates_email_with_verification(
        self, test_email: str, test_email_alt: str
    ) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email, password_hash="hash")
        user_repo.get_by_id_for_update.return_value = user
        updated_user = User(
            id=user.id,
            email=test_email_alt,
            password_hash="hash",
            updated_at=datetime.now(UTC),
        )
        user_repo.update.return_value = updated_user
        verification_service = AsyncMock()
        token_repo = AsyncMock()
        service = _make_service(
            user_repo=user_repo,
            verification_service=verification_service,
            token_repo=token_repo,
        )
        result = await service.update_user(
            user_id=user.id,
            email=test_email_alt,
            verification_token="V" * 43,
        )
        assert result.email == updated_user.email
        assert result.updated_at == updated_user.updated_at
        verification_service.verify_operation_token.assert_awaited_once_with(
            token="V" * 43,
            contact=test_email_alt,
            expected_action=VerificationActionType.EMAIL_CHANGE,
        )
        user_repo.update.assert_awaited_once_with(
            user_id=user.id, email=test_email_alt, password_hash=None
        )

    async def test_skips_verification_if_email_not_changed(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(
            id=uuid.uuid4(),
            email=test_email,
            password_hash="hash",
            updated_at=datetime.now(UTC),
        )
        user_repo.get_by_id_for_update.return_value = user
        user_repo.update.return_value = user
        verification_service = AsyncMock()
        service = _make_service(user_repo=user_repo, verification_service=verification_service)
        await service.update_user(user_id=user.id, email=test_email)
        verification_service.verify_operation_token.assert_not_awaited()


@pytest.mark.anyio
class TestUserServiceUpdateUserAdmin:
    async def test_success_updates_admin_fields(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(
            id=uuid.uuid4(),
            email=test_email,
            role=UserRole.USER,
            is_banned=False,
            updated_at=datetime.now(UTC),
        )
        user_repo.get_by_id_for_update.return_value = user
        updated_user = User(
            id=user.id,
            email=user.email,
            role=UserRole.ADMIN,
            is_banned=True,
            updated_at=datetime.now(UTC),
        )
        user_repo.update.return_value = updated_user
        token_repo = AsyncMock()
        service = _make_service(user_repo=user_repo, token_repo=token_repo)
        await service.update_user_admin(user_id=user.id, is_banned=True, role=UserRole.ADMIN)
        user_repo.update.assert_awaited_once()
        token_repo.revoke_all_by_user_id.assert_awaited_once()

    async def test_raises_user_not_found_if_user_missing(self) -> None:
        user_repo = AsyncMock()
        user_repo.get_by_id_for_update.return_value = None
        service = _make_service(user_repo=user_repo)
        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_user_admin(user_id=uuid.uuid4())
        assert_exception_details(exc_info, 404, UserNotFoundError)

    async def test_raises_user_not_found_on_no_result_found(self, test_email: str) -> None:
        user_repo = AsyncMock()
        user = User(id=uuid.uuid4(), email=test_email)
        user_repo.get_by_id_for_update.return_value = user
        user_repo.update.side_effect = NoResultFound()
        service = _make_service(user_repo=user_repo)
        with pytest.raises(UserNotFoundError) as exc_info:
            await service.update_user_admin(user_id=user.id)
        assert_exception_details(exc_info, 404, UserNotFoundError)
