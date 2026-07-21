from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import (
    InvalidCredentialsError,
    TokenPasswordAttemptsBlockedError,
    UserBannedError,
)
from app.core.security import hash_contact, hash_token
from app.models.domain import Token
from app.schemas.tokens import PasswordAttemptSessionData


@pytest.mark.anyio
class TestCreateToken:
    async def test_success_create_token(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        valid_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)

        payload = {"email": user.email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" not in data

        stmt = select(Token).where(Token.user_id == user.id, Token.is_active)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()

        assert token_record is not None
        assert token_record.is_active is True

        expected_hash = hash_token(data["access_token"])
        assert token_record.token_hash == expected_hash

    @pytest.mark.parametrize(
        "invalid_email",
        ["invalid", "test@", ""],
    )
    async def test_validation_errors_invalid_email(
        self,
        http_client: AsyncClient,
        invalid_email: str,
        valid_test_password: str,
    ) -> None:
        payload = {"email": invalid_email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

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
    ) -> None:
        payload = {"email": "test@example.com", "password": invalid_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_business_error_invalid_credentials(
        self,
        http_client: AsyncClient,
        create_test_user,
        valid_test_password: str,
        wrong_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)

        payload = {"email": user.email, "password": wrong_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert data["detail"] == InvalidCredentialsError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_banned_user(
        self,
        http_client: AsyncClient,
        create_test_user,
        valid_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_banned=True)

        payload = {"email": user.email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert data["detail"] == UserBannedError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_deleted_user(
        self,
        http_client: AsyncClient,
        create_test_user,
        valid_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password, is_deleted=True)

        payload = {"email": user.email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert data["detail"] == InvalidCredentialsError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    @freeze_time("2026-01-01 12:00:00")
    async def test_business_error_password_attempts_blocked_returns_423(
        self,
        http_client: AsyncClient,
        redis_client,
        create_test_user,
        valid_test_password: str,
        wrong_test_password: str,
        faker,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        email_hash = hash_contact(user.email)

        now = datetime.now(UTC)
        blocked_until = now + timedelta(minutes=10)
        remaining_seconds = 600

        session = PasswordAttemptSessionData(
            failed_attempts=3,
            window_start=now,
            blocked_until=blocked_until,
            last_block_ts=now,
        )
        await redis_client.set(
            f"password_attempts:{email_hash}",
            session.model_dump_json(),
            ex=3600,
        )

        payload = {"email": user.email, "password": wrong_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)

        assert response.status_code == 423
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 423

        expected_exception = TokenPasswordAttemptsBlockedError(remaining_seconds=remaining_seconds)
        assert data["detail"] == expected_exception.detail

        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
        assert response.headers["content-type"] == "application/problem+json"

    async def test_integration_three_failed_attempts_triggers_block(
        self,
        http_client: AsyncClient,
        redis_client,
        create_test_user,
        valid_test_password: str,
        wrong_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        email_hash = hash_contact(user.email)

        payload = {"email": user.email, "password": wrong_test_password}

        for _attempt in range(3):
            response = await http_client.post("/api/v1/tokens", json=payload)
            assert response.status_code == 401

        session_key = f"password_attempts:{email_hash}"
        session_data = await redis_client.get(session_key)
        assert session_data is not None

        parsed = PasswordAttemptSessionData.model_validate_json(session_data)
        assert parsed.failed_attempts == 3
        assert parsed.blocked_until is not None

        response = await http_client.post("/api/v1/tokens", json=payload)
        assert response.status_code == 423

    async def test_integration_successful_login_resets_session(
        self,
        http_client: AsyncClient,
        redis_client,
        create_test_user,
        valid_test_password: str,
        wrong_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        email_hash = hash_contact(user.email)

        payload_wrong = {"email": user.email, "password": wrong_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload_wrong)
        assert response.status_code == 401

        session_key = f"password_attempts:{email_hash}"
        assert await redis_client.exists(session_key) == 1

        payload_correct = {"email": user.email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload_correct)
        assert response.status_code == 201

        assert await redis_client.exists(session_key) == 0

    async def test_integration_user_not_found_does_not_create_redis_session(
        self,
        http_client: AsyncClient,
        redis_client,
        valid_test_password: str,
        faker,
    ) -> None:
        email = faker.email().lower()
        email_hash = hash_contact(email)

        payload = {"email": email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)
        assert response.status_code == 401

        session_key = f"password_attempts:{email_hash}"
        assert await redis_client.exists(session_key) == 0

    async def test_integration_successful_login_revokes_previous_tokens(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        valid_test_password: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)

        initial_token = Token(token_hash="old_hashed_token", user_id=user.id, is_active=True)
        db_session.add(initial_token)
        await db_session.flush()

        payload = {"email": user.email, "password": valid_test_password}
        response = await http_client.post("/api/v1/tokens", json=payload)
        assert response.status_code == 201

        stmt = select(Token).where(Token.user_id == user.id)
        result = await db_session.execute(stmt)
        tokens = result.scalars().all()

        assert len(tokens) == 2
        active_tokens = [t for t in tokens if t.is_active]
        assert len(active_tokens) == 1
        assert active_tokens[0].token_hash != "old_hashed_token"
        assert initial_token.is_active is False
