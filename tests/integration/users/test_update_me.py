import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.endpoints import users as users_endpoint
from app.core.exceptions import (
    ContactNotVerifiedError,
    CurrentPasswordInvalidError,
    EmailAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
)
from app.core.security import hash_token, verify_password
from app.models.domain import User, UserRole
from app.schemas.responses import UserUpdateResponse
from app.schemas.verification import VerificationActionType
from app.services import aliases as aliases_service_module


@pytest.mark.anyio
class TestUpdateUserMe:
    async def test_success_update_email(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        create_verification_token,
        redis_client,
        valid_test_password,
        generate_test_email,
        monkeypatch,
    ) -> None:
        mock_workflow = MagicMock()
        mock_group = MagicMock(return_value=mock_workflow)
        monkeypatch.setattr(users_endpoint, "group", mock_group)
        monkeypatch.setattr(
            aliases_service_module.AliasService,
            "get_active_alias_ids",
            AsyncMock(return_value=[uuid.uuid4()]),
        )

        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        new_email = generate_test_email(prefix="update")

        raw_token = "E3fM6pR9qS2vN5wT8yU1zA4bD7cF0eG3hJ6kL9mP2xQ"
        token_key = f"vtoken:{hash_token(raw_token)}"
        await create_verification_token(
            email=new_email,
            action_type=VerificationActionType.EMAIL_CHANGE,
            raw_token=raw_token,
        )

        payload = {"email": new_email, "verification_token": raw_token}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 200
        data = UserUpdateResponse(**response.json())
        assert data.email == new_email
        assert data.updated_at is not None

        result = await db_session.execute(select(User).where(User.email == new_email))
        updated_user = result.scalar_one()
        assert updated_user.email == new_email
        assert updated_user.updated_at is not None

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

        verification_exists = await redis_client.exists(token_key)
        assert verification_exists == 0

        mock_group.assert_called_once()
        mock_workflow.apply_async.assert_called_once()

    async def test_success_update_password(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password,
        new_valid_test_password,
        monkeypatch,
    ) -> None:
        mock_group = MagicMock()
        monkeypatch.setattr(users_endpoint, "group", mock_group)

        password = valid_test_password
        user = await create_test_user(password=password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}
        new_password = new_valid_test_password

        payload = {
            "new_password": new_password,
            "current_password": password,
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 200
        data = UserUpdateResponse(**response.json())
        assert data.updated_at is not None

        result = await db_session.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert verify_password(new_password, updated_user.password_hash)
        assert not verify_password(password, updated_user.password_hash)
        assert updated_user.updated_at is not None

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

        mock_group.assert_not_called()

    async def test_success_update_both_email_and_password(
        self,
        http_client: AsyncClient,
        db_session,
        redis_client,
        create_test_user,
        create_auth_token,
        create_verification_token,
        valid_test_password,
        new_valid_test_password,
        generate_test_email,
        monkeypatch,
    ) -> None:
        mock_workflow = MagicMock()
        mock_group = MagicMock(return_value=mock_workflow)
        monkeypatch.setattr(users_endpoint, "group", mock_group)
        monkeypatch.setattr(
            aliases_service_module.AliasService,
            "get_active_alias_ids",
            AsyncMock(return_value=[uuid.uuid4()]),
        )

        password = valid_test_password
        user = await create_test_user(password=password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}
        new_email = generate_test_email(prefix="update")
        new_password = new_valid_test_password

        raw_token = "B0thUpd4t3T0k3nF0rT3st1ngPurp0s3s0n1y123456"
        token_key = f"vtoken:{hash_token(raw_token)}"
        await create_verification_token(
            email=new_email,
            action_type=VerificationActionType.EMAIL_CHANGE,
            raw_token=raw_token,
        )

        payload = {
            "email": new_email,
            "new_password": new_password,
            "current_password": password,
            "verification_token": raw_token,
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 200
        data = UserUpdateResponse(**response.json())
        assert data.email == new_email
        assert data.updated_at is not None

        result = await db_session.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.email == new_email
        assert verify_password(new_password, updated_user.password_hash)
        assert not verify_password(password, updated_user.password_hash)
        assert updated_user.updated_at is not None

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

        verification_exists = await redis_client.exists(token_key)
        assert verification_exists == 0

        mock_group.assert_called_once()
        mock_workflow.apply_async.assert_called_once()

    async def test_business_error_user_not_found(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password,
        override_current_user_id,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_deleted=True)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        override_current_user_id(user.id)

        payload = {"new_password": "NewP@ss123!", "current_password": valid_test_password}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 404
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 404
        assert data["detail"] == UserNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

    async def test_business_error_user_banned(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password,
        override_current_user_id,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_banned=True)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        override_current_user_id(user.id)

        payload = {"new_password": "NewP@ss123!", "current_password": valid_test_password}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert data["detail"] == UserBannedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

    @pytest.mark.parametrize(
        "invalid_email",
        ["invalid", "test@", ""],
    )
    async def test_validation_errors_invalid_email(
        self,
        http_client: AsyncClient,
        invalid_email: str,
        authenticated_headers,
    ) -> None:
        headers = await authenticated_headers()
        payload = {
            "email": invalid_email,
            "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    @pytest.mark.parametrize(
        "invalid_password",
        ["short", ""],
    )
    async def test_validation_errors_invalid_password(
        self,
        http_client: AsyncClient,
        invalid_password: str,
        authenticated_headers,
        valid_test_password,
    ) -> None:
        headers = await authenticated_headers()
        payload = {"new_password": invalid_password, "current_password": valid_test_password}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW"},
        ],
    )
    async def test_validation_errors_missing_fields(
        self,
        http_client: AsyncClient,
        payload: dict,
        authenticated_headers,
    ) -> None:
        headers = await authenticated_headers()
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_business_error_current_password_invalid(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        valid_test_password,
        new_valid_test_password,
    ) -> None:
        headers = await authenticated_headers()
        wrong_password = "WrongP@ssw0rd123!"
        new_password = new_valid_test_password

        payload = {
            "new_password": new_password,
            "current_password": wrong_password,
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == CurrentPasswordInvalidError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_contact_not_verified(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        generate_test_email,
    ) -> None:
        headers = await authenticated_headers()
        new_email = generate_test_email(prefix="update")

        payload = {
            "email": new_email,
            "verification_token": "invalid_token_not_in_redis_1234567890123456",
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == ContactNotVerifiedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_contact_not_verified_false(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        create_verification_token,
        generate_test_email,
    ) -> None:
        headers = await authenticated_headers()
        new_email = generate_test_email(prefix="update")

        raw_token = "wrong_action_token_123456789012345678901234"
        await create_verification_token(
            email=new_email,
            action_type=VerificationActionType.PASSWORD_RESET,
            raw_token=raw_token,
        )

        payload = {
            "email": new_email,
            "verification_token": raw_token,
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == ContactNotVerifiedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_email_already_exists(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        create_test_user,
        create_verification_token,
        generate_test_email,
        valid_test_password,
    ) -> None:
        headers = await authenticated_headers()
        existing_email = generate_test_email(prefix="conflict")

        await create_test_user(email=existing_email, password=valid_test_password)

        raw_token = "C0nf1ictT0k3nF0rT3st1ngPurp0s3s0n1y12345678"
        await create_verification_token(
            email=existing_email,
            action_type=VerificationActionType.EMAIL_CHANGE,
            raw_token=raw_token,
        )

        payload = {"email": existing_email, "verification_token": raw_token}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 409
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 409
        assert data["detail"] == EmailAlreadyExistsError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_validation_error_password_change_without_current_password(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        new_valid_test_password,
    ) -> None:
        headers = await authenticated_headers()
        new_password = new_valid_test_password

        payload = {"new_password": new_password}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_token_not_revoked_on_validation_error(
        self,
        http_client: AsyncClient,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        hashed = hash_token(active_token)
        before = await redis_client.get(f"tkn:{hashed}")
        assert before is not None

        payload = {
            "email": "new@example.com",
            "verification_token": "invalid_token_not_in_redis_1234567890123456",
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 400
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is not None

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
        create_test_user,
        valid_test_password,
    ) -> None:
        response = await http_client.patch("/api/v1/users/me", json={"email": "new@example.com"})

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["detail"], str)
