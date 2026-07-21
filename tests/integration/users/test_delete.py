import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import ContactNotVerifiedError, UserBannedError
from app.core.security import hash_token
from app.models.domain import Token, User, UserRole
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
        valid_test_password: str,
        override_current_user_id,
        dummy_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        token_key = f"vtoken:{hash_token(dummy_verification_token)}"
        await create_verification_token(
            email=user.email,
            action_type=VerificationActionType.USER_DELETION,
            raw_token=dummy_verification_token,
        )

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": dummy_verification_token},
            headers=headers,
        )

        assert response.status_code == 204
        assert response.content == b""

        result = await db_session.execute(select(User).where(User.id == user.id))
        deleted_user = result.scalar_one_or_none()
        assert deleted_user is not None
        assert deleted_user.deleted_at is not None

        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is False

        after_verification = await redis_client.get(token_key)
        assert after_verification is None

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"verification_token": "short"},
            {"verification_token": "a" * 44},
            {"verification_token": 123},
        ],
    )
    async def test_validation_errors_invalid_payload(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        payload: dict,
    ) -> None:
        headers = await authenticated_headers()
        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json=payload,
            headers=headers,
        )

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
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password: str,
        override_current_user_id,
        invalid_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": invalid_verification_token},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 400
        assert isinstance(data["detail"], str)
        assert data["detail"] == ContactNotVerifiedError().detail
        assert isinstance(data["instance"], str)

        result = await db_session.execute(select(User).where(User.id == user.id))
        existing_user = result.scalar_one_or_none()
        assert existing_user is not None
        assert existing_user.deleted_at is None

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True

    async def test_business_error_user_banned(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password: str,
        override_current_user_id,
        invalid_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_banned=True)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": invalid_verification_token},
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

        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is False

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
        valid_test_password: str,
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
        db_session,
        create_test_user,
        create_auth_token,
        create_verification_token,
        redis_client,
        valid_test_password: str,
        override_current_user_id,
        dummy_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        await create_verification_token(
            email=user.email,
            action_type=VerificationActionType.USER_DELETION,
            raw_token=dummy_verification_token,
        )

        override_current_user_id(user.id)

        first_response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": dummy_verification_token},
            headers=headers,
        )
        assert first_response.status_code == 204

        second_response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": dummy_verification_token},
            headers=headers,
        )
        assert second_response.status_code == 204

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is False

    async def test_ghost_token_cleanup_when_user_already_deleted(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        redis_client,
        valid_test_password: str,
        override_current_user_id,
        dummy_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_deleted=True)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True

        override_current_user_id(user.id)

        response = await http_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"verification_token": dummy_verification_token},
            headers=headers,
        )

        assert response.status_code == 204
        assert response.content == b""

        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is False
