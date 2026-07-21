import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import (
    ContactNotVerifiedError,
    EmailAlreadyExistsError,
    UserBannedError,
)
from app.core.security import hash_token, verify_password
from app.models.domain import User, UserRole
from app.schemas.responses import UserCreateResponse
from app.schemas.verification import VerificationActionType


@pytest.mark.anyio
class TestCreateUser:
    async def test_success_creates_user(
        self,
        http_client: AsyncClient,
        db_session,
        redis_client,
        create_verification_token,
        valid_test_password: str,
        generate_test_email,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="create")
        password = valid_test_password

        token_key = f"vtoken:{hash_token(dummy_verification_token)}"
        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "password": password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 201
        UserCreateResponse(**response.json())

        result = await db_session.execute(select(User).where(User.email == email))
        created_user = result.scalar_one_or_none()
        assert created_user is not None
        assert created_user.email == email
        assert created_user.password_hash is not None
        assert created_user.password_hash != password
        assert created_user.is_banned is False
        assert created_user.role == UserRole.USER
        assert created_user.deleted_at is None

        token_exists = await redis_client.exists(token_key)
        assert token_exists == 0

    @pytest.mark.parametrize(
        "invalid_email",
        ["invalid", "test@", ""],
    )
    async def test_validation_errors_invalid_email(
        self,
        http_client: AsyncClient,
        invalid_email: str,
        valid_test_password: str,
        dummy_verification_token: str,
    ) -> None:
        payload = {
            "email": invalid_email,
            "password": valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.post("/api/v1/users", json=payload)

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
        dummy_verification_token: str,
    ) -> None:
        payload = {
            "email": "test@example.com",
            "password": invalid_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.post("/api/v1/users", json=payload)

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
            {
                "email": "test@example.com",
                "verification_token": "dummy_token",
            },
            {
                "password": "TestP@ssw0rd123!",
                "verification_token": "dummy_token",
            },
            {"verification_token": "dummy_token"},
            {"email": "test@example.com", "password": "TestP@ssw0rd123!"},
        ],
    )
    async def test_validation_errors_missing_fields(
        self, http_client: AsyncClient, payload: dict
    ) -> None:
        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_business_error_contact_not_verified(
        self,
        http_client: AsyncClient,
        valid_test_password: str,
        generate_test_email,
        invalid_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="create")
        payload = {
            "email": email,
            "password": valid_test_password,
            "verification_token": invalid_verification_token,
        }

        response = await http_client.post("/api/v1/users", json=payload)

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
        create_verification_token,
        valid_test_password: str,
        generate_test_email,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="create")

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.PASSWORD_RESET,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "password": valid_test_password,
            "verification_token": dummy_verification_token,
        }

        response = await http_client.post("/api/v1/users", json=payload)

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
        create_verification_token,
        valid_test_password: str,
        generate_test_email,
        dummy_verification_token: str,
        second_dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="create")
        password = valid_test_password

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=dummy_verification_token,
        )

        first_payload = {
            "email": email,
            "password": password,
            "verification_token": dummy_verification_token,
        }
        first_response = await http_client.post("/api/v1/users", json=first_payload)
        assert first_response.status_code == 201

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=second_dummy_verification_token,
        )

        second_payload = {
            "email": email,
            "password": password,
            "verification_token": second_dummy_verification_token,
        }
        second_response = await http_client.post("/api/v1/users", json=second_payload)

        assert second_response.status_code == 409
        data = second_response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 409
        assert data["detail"] == EmailAlreadyExistsError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_success_reactivates_soft_deleted_user(
        self,
        http_client: AsyncClient,
        db_session,
        redis_client,
        create_test_user,
        create_verification_token,
        valid_test_password: str,
        new_valid_test_password: str,
        generate_test_email,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="reactivate")
        old_password = valid_test_password
        new_password = new_valid_test_password

        user = await create_test_user(email=email, password=old_password, is_deleted=True)

        token_key = f"vtoken:{hash_token(dummy_verification_token)}"
        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "password": new_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 201
        UserCreateResponse(**response.json())

        result = await db_session.execute(
            select(User).where(User.email == email).execution_options(populate_existing=True)
        )
        reactivated_user = result.scalar_one_or_none()
        assert reactivated_user is not None
        assert reactivated_user.id == user.id
        assert reactivated_user.deleted_at is None
        assert verify_password(reactivated_user.password_hash, new_password)
        assert not verify_password(reactivated_user.password_hash, old_password)

        token_exists = await redis_client.exists(token_key)
        assert token_exists == 0

    async def test_business_error_reactivation_of_banned_user(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_verification_token,
        valid_test_password: str,
        generate_test_email,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="banned_react")

        user = await create_test_user(
            email=email, password=valid_test_password, is_banned=True, is_deleted=True
        )

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "password": valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert data["detail"] == UserBannedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

        result = await db_session.execute(
            select(User).where(User.id == user.id).execution_options(populate_existing=True)
        )
        banned_user = result.scalar_one_or_none()
        assert banned_user.deleted_at is not None
