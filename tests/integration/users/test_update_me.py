import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1.endpoints import users as users_endpoint
from app.core.security import hash_token
from app.models.domain import Token, User, UserRole
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
        valid_test_password: str,
        test_email_alt: str,
        monkeypatch,
        dummy_verification_token: str,
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

        token_key = f"vtoken:{hash_token(dummy_verification_token)}"
        await create_verification_token(
            email=test_email_alt,
            action_type=VerificationActionType.EMAIL_CHANGE,
            raw_token=dummy_verification_token,
        )

        payload = {"email": test_email_alt, "verification_token": dummy_verification_token}
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 200
        data = UserUpdateResponse(**response.json())
        assert data.email == test_email_alt
        assert data.updated_at is not None

        result = await db_session.execute(select(User).where(User.email == test_email_alt))
        updated_user = result.scalar_one()
        assert updated_user.email == test_email_alt
        assert updated_user.updated_at is not None

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is False

        verification_exists = await redis_client.exists(token_key)
        assert verification_exists == 0

        mock_group.assert_called_once()
        mock_workflow.apply_async.assert_called_once()

    async def test_token_not_revoked_on_validation_error(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_auth_token,
        valid_test_password: str,
        test_email_alt: str,
        invalid_verification_token: str,
    ) -> None:
        user = await create_test_user(password=valid_test_password)
        active_token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {active_token}"}

        hashed = hash_token(active_token)
        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True

        payload = {
            "email": test_email_alt,
            "verification_token": invalid_verification_token,
        }
        response = await http_client.patch("/api/v1/users/me", json=payload, headers=headers)

        assert response.status_code == 400

        stmt = select(Token).where(Token.token_hash == hashed)
        result = await db_session.execute(stmt)
        token_record = result.scalar_one_or_none()
        assert token_record is not None
        assert token_record.is_active is True
