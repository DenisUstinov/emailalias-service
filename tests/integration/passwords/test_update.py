import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import (
    ContactNotVerifiedError,
    UserBannedError,
    UserNotFoundError,
)
from app.core.security import hash_token, verify_password
from app.models.domain import User
from app.schemas.verification import VerificationActionType


@pytest.mark.anyio
class TestUpdatePassword:
    async def test_success_update_password(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        redis_client,
        valid_test_password: str,
        new_valid_test_password: str,
        generate_test_email,
        create_verification_token,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="pwd_success")
        await create_test_user(email=email, password=valid_test_password)

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.PASSWORD_RESET,
            raw_token=dummy_verification_token,
        )
        token_key = f"vtoken:{hash_token(dummy_verification_token)}"

        payload = {
            "email": email,
            "new_password": new_valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.patch("/api/v1/passwords", json=payload)

        assert response.status_code == 204
        assert response.content == b""

        result = await db_session.execute(select(User).where(User.email == email))
        updated_user = result.scalar_one()
        assert verify_password(updated_user.password_hash, new_valid_test_password)
        assert not verify_password(updated_user.password_hash, valid_test_password)

        token_exists = await redis_client.exists(token_key)
        assert token_exists == 0

    async def test_business_error_contact_not_verified(
        self,
        http_client: AsyncClient,
        create_test_user,
        valid_test_password: str,
        new_valid_test_password: str,
        generate_test_email,
        invalid_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="pwd_not_verified")
        await create_test_user(email=email, password=valid_test_password)

        payload = {
            "email": email,
            "new_password": new_valid_test_password,
            "verification_token": invalid_verification_token,
        }
        response = await http_client.patch("/api/v1/passwords", json=payload)

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
        create_test_user,
        valid_test_password: str,
        new_valid_test_password: str,
        generate_test_email,
        create_verification_token,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="pwd_wrong_action")
        await create_test_user(email=email, password=valid_test_password)

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.USER_CREATION,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "new_password": new_valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.patch("/api/v1/passwords", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert data["detail"] == ContactNotVerifiedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_user_not_found(
        self,
        http_client: AsyncClient,
        new_valid_test_password: str,
        generate_test_email,
        create_verification_token,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="pwd_not_found")

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.PASSWORD_RESET,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "new_password": new_valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.patch("/api/v1/passwords", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 404
        assert data["detail"] == UserNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_user_banned(
        self,
        http_client: AsyncClient,
        create_test_user,
        wrong_test_password: str,
        new_valid_test_password: str,
        generate_test_email,
        create_verification_token,
        dummy_verification_token: str,
    ) -> None:
        email = generate_test_email(prefix="pwd_banned")
        await create_test_user(email=email, password=wrong_test_password, is_banned=True)

        await create_verification_token(
            email=email,
            action_type=VerificationActionType.PASSWORD_RESET,
            raw_token=dummy_verification_token,
        )

        payload = {
            "email": email,
            "new_password": new_valid_test_password,
            "verification_token": dummy_verification_token,
        }
        response = await http_client.patch("/api/v1/passwords", json=payload)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert data["detail"] == UserBannedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
