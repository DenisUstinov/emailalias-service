import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.exceptions import (
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    UserBannedError,
)
from app.core.security import hash_token, verify_password
from app.models.domain import User, UserRole
from app.schemas.responses import UserCreateResponse
from app.schemas.verification import (
    VerificationActionType,
    VerificationTokenData,
)


@pytest.mark.anyio
class TestCreateUser:
    async def test_success_creates_user(
        self,
        http_client: AsyncClient,
        db_session,
        redis_client,
        valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="create")
        password = valid_test_password

        raw_token = "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW"
        token_hash = hash_token(raw_token)
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        payload = {"email": email, "password": password, "verification_token": raw_token}
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
        valid_test_password,
    ) -> None:
        payload = {
            "email": invalid_email,
            "password": valid_test_password,
            "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
        }
        response = await http_client.post("/api/v1/users", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data.get("detail"), list)

    @pytest.mark.parametrize(
        "invalid_password",
        ["short", ""],
    )
    async def test_validation_errors_invalid_password(
        self,
        http_client: AsyncClient,
        invalid_password: str,
    ) -> None:
        payload = {
            "email": "test@example.com",
            "password": invalid_password,
            "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
        }
        response = await http_client.post("/api/v1/users", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data.get("detail"), list)

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "email": "test@example.com",
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            },
            {
                "password": "TestP@ssw0rd123!",
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            },
            {"verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW"},
            {"email": "test@example.com", "password": "TestP@ssw0rd123!"},
        ],
    )
    async def test_validation_errors_missing_fields(
        self, http_client: AsyncClient, payload: dict
    ) -> None:
        response = await http_client.post("/api/v1/users", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data.get("detail"), list)

    async def test_business_error_email_not_verified(
        self,
        http_client: AsyncClient,
        valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="create")
        payload = {
            "email": email,
            "password": valid_test_password,
            "verification_token": "invalid_token_not_in_redis_1234567890123456",
        }

        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == EmailNotVerifiedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_email_not_verified_false(
        self,
        http_client: AsyncClient,
        redis_client,
        valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="create")
        payload = {
            "email": email,
            "password": valid_test_password,
            "verification_token": "wrong_action_token_123456789012345678901234",
        }

        token_hash = hash_token("wrong_action_token_123456789012345678901234")
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.PASSWORD_RESET,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        response = await http_client.post("/api/v1/users", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == EmailNotVerifiedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_email_already_exists(
        self,
        http_client: AsyncClient,
        redis_client,
        valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="create")
        password = valid_test_password

        raw_token = "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW"
        token_hash = hash_token(raw_token)
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        first_payload = {"email": email, "password": password, "verification_token": raw_token}
        first_response = await http_client.post("/api/v1/users", json=first_payload)
        assert first_response.status_code == 201

        raw_token_2 = "D9eL2kP5nQ8vM1wR4tY7uZ0sA3bC6dE9gH2jN5pM8xW"
        token_hash_2 = hash_token(raw_token_2)
        token_key_2 = f"vtoken:{token_hash_2}"
        token_data_2 = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
        )
        await redis_client.set(
            token_key_2,
            token_data_2.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        second_payload = {"email": email, "password": password, "verification_token": raw_token_2}
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
        valid_test_password,
        new_valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="reactivate")
        old_password = valid_test_password
        new_password = new_valid_test_password

        user = await create_test_user(email=email, password=old_password)

        await db_session.execute(
            update(User).where(User.id == user.id).values(deleted_at=func.now())
        )
        await db_session.flush()

        raw_token = "R3aCt1v4t3T0k3nF0rT3st1ngPurp0s3sOn1y123456"
        token_hash = hash_token(raw_token)
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        payload = {"email": email, "password": new_password, "verification_token": raw_token}
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
        assert verify_password(new_password, reactivated_user.password_hash)
        assert not verify_password(old_password, reactivated_user.password_hash)

        token_exists = await redis_client.exists(token_key)
        assert token_exists == 0

    async def test_business_error_reactivation_of_banned_user(
        self,
        http_client: AsyncClient,
        db_session,
        redis_client,
        create_test_user,
        valid_test_password,
        generate_test_email,
    ) -> None:
        email = generate_test_email(prefix="banned_react")
        user = await create_test_user(email=email, password=valid_test_password, is_banned=True)

        await db_session.execute(
            update(User).where(User.id == user.id).values(deleted_at=func.now())
        )
        await db_session.flush()

        raw_token = "B4nn3dR34ctT0k3nF0rT3st1ngPurp0s3s0n1y12345"
        token_hash = hash_token(raw_token)
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )

        payload = {"email": email, "password": valid_test_password, "verification_token": raw_token}
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
