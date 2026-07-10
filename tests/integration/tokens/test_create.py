import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import InvalidCredentialsError, UserBannedError
from app.core.security import hash_token
from app.models.domain import Token


@pytest.mark.anyio
class TestCreateToken:
    async def test_success_create_token(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        valid_test_password,
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
        valid_test_password,
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
        valid_test_password,
    ) -> None:
        user = await create_test_user(password=valid_test_password)

        payload = {"email": user.email, "password": "WrongP@ssw0rd123!"}
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
        valid_test_password,
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
        valid_test_password,
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
