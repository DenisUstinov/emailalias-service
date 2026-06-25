import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import EmailNotVerifiedError, UserBannedError
from app.core.security import hash_token
from app.models.domain import User, UserRole
from app.schemas.verification import VerificationActionType


@pytest.mark.anyio
class TestDeleteUserMe:
    async def test_success_deletes_user(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        create_verification_token,
        redis_client,
        valid_test_password,
        override_current_user_id,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        raw_token = "D9eL2kP5nQ8vM1wR4tY7uZ0sA3bC6dE9gH2jN5pM8xW"
        token_key = f"vtoken:{hash_token(raw_token)}"
        await create_verification_token(
            email=user.email,
            action_type=VerificationActionType.USER_DELETION,
            raw_token=raw_token,
        )

        hashed = hash_token(active_token)
        before_delete = await redis_client.get(f"tkn:{hashed}")
        assert before_delete is not None

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": raw_token},
            headers=headers,
        )

        assert response.status_code == 204
        assert response.content == b""

        result = await db_session.execute(select(User).where(User.id == user.id))
        deleted_user = result.scalar_one_or_none()
        assert deleted_user is not None
        assert deleted_user.deleted_at is not None

        after_delete = await redis_client.get(f"tkn:{hashed}")
        assert after_delete is None

        after_verification = await redis_client.get(token_key)
        assert after_verification is None

    async def test_business_error_email_not_verified(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password,
        override_current_user_id,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": "invalid_token_not_in_redis_1234567890123456"},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert isinstance(data["detail"], str)
        assert data["detail"] == EmailNotVerifiedError().detail
        assert isinstance(data["instance"], str)

        result = await db_session.execute(select(User).where(User.id == user.id))
        existing_user = result.scalar_one_or_none()
        assert existing_user is not None
        assert existing_user.deleted_at is None

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is not None

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

        hashed = hash_token(active_token)
        before_attempt = await redis_client.get(f"tkn:{hashed}")
        assert before_attempt is not None

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": "invalid_token_not_in_redis_1234567890123456"},
            headers=headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert isinstance(data["detail"], str)
        assert data["detail"] == UserBannedError().detail
        assert isinstance(data["instance"], str)

        after_attempt = await redis_client.get(f"tkn:{hashed}")
        assert after_attempt is None

        result = await db_session.execute(select(User).where(User.id == user.id))
        banned_user = result.scalar_one_or_none()
        assert banned_user is not None
        assert banned_user.is_banned is True
        assert banned_user.deleted_at is None

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        valid_test_password,
    ) -> None:
        user = await create_test_user(password=valid_test_password)

        response = await http_client.request("DELETE", "/api/v1/users/me")

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

        result = await db_session.execute(select(User).where(User.id == user.id))
        existing_user = result.scalar_one_or_none()
        assert existing_user is not None
        assert existing_user.deleted_at is None

    async def test_idempotency_second_call_returns_204(
        self,
        http_client: AsyncClient,
        create_test_user,
        create_auth_token,
        create_verification_token,
        redis_client,
        valid_test_password,
        override_current_user_id,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        raw_token = "1d3mp0t3ncyT0k3nF0rT3st1ngPurp0s3s0n1y12345"
        await create_verification_token(
            email=user.email,
            action_type=VerificationActionType.USER_DELETION,
            raw_token=raw_token,
        )

        override_current_user_id(user.id)

        first_response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": raw_token},
            headers=headers,
        )
        assert first_response.status_code == 204

        second_response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": raw_token},
            headers=headers,
        )
        assert second_response.status_code == 204

        hashed = hash_token(active_token)
        revoked = await redis_client.get(f"tkn:{hashed}")
        assert revoked is None

    async def test_ghost_token_cleanup_when_user_already_deleted(
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

        hashed = hash_token(active_token)
        before_attempt = await redis_client.get(f"tkn:{hashed}")
        assert before_attempt is not None

        override_current_user_id(user.id)

        verification_token = "a" * 43

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": verification_token},
            headers=headers,
        )

        assert response.status_code == 204
        assert response.content == b""

        after_attempt = await redis_client.get(f"tkn:{hashed}")
        assert after_attempt is None
