import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.domain import Alias, AliasStatus, UserRole


@pytest.mark.anyio
class TestDeleteAlias:
    async def test_success_deletes_alias_and_queues_task(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_test_domain,
        create_auth_token,
        monkeypatch,
    ) -> None:
        mock_task = MagicMock()
        monkeypatch.setattr("app.api.v1.endpoints.aliases.deprovision_alias_task", mock_task)

        user = await create_test_user(password="TestP@ss123!")
        domain = await create_test_domain(fqdn="delete-test.com", is_default=True)

        alias = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="test",
            random_part="abc123",
            status=AliasStatus.ACTIVE,
        )
        db_session.add(alias)
        await db_session.flush()

        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        response = await http_client.delete(f"/api/v1/aliases/{alias.id}", headers=headers)

        assert response.status_code == 204
        assert response.content == b""

        result = await db_session.execute(
            select(Alias).where(Alias.id == alias.id).execution_options(populate_existing=True)
        )
        updated_alias = result.scalar_one_or_none()
        assert updated_alias is not None
        assert updated_alias.status == AliasStatus.DELETED

        mock_task.apply_async.assert_called_once()
        call_args = mock_task.apply_async.call_args
        assert call_args[1]["args"][0] == str(alias.id)

    async def test_idempotency_second_call_returns_204(
        self,
        http_client: AsyncClient,
        db_session,
        create_test_user,
        create_test_domain,
        create_auth_token,
        monkeypatch,
    ) -> None:
        mock_task = MagicMock()
        monkeypatch.setattr("app.api.v1.endpoints.aliases.deprovision_alias_task", mock_task)

        user = await create_test_user(password="TestP@ss123!")
        domain = await create_test_domain(fqdn="idempotent-test.com", is_default=True)

        alias = Alias(
            user_id=user.id,
            domain_id=domain.id,
            local_part="test",
            random_part="abc123",
            status=AliasStatus.DELETED,
        )
        db_session.add(alias)
        await db_session.flush()

        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        first_response = await http_client.delete(f"/api/v1/aliases/{alias.id}", headers=headers)
        assert first_response.status_code == 204

        second_response = await http_client.delete(f"/api/v1/aliases/{alias.id}", headers=headers)
        assert second_response.status_code == 204

        assert mock_task.apply_async.call_count == 2

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
    ) -> None:
        response = await http_client.delete(f"/api/v1/aliases/{uuid.uuid4()}")

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_alias_not_found_or_not_owned(
        self,
        http_client: AsyncClient,
        create_test_user,
        create_auth_token,
    ) -> None:
        user = await create_test_user(password="TestP@ss123!")
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        non_existent_id = uuid.uuid4()

        response = await http_client.delete(f"/api/v1/aliases/{non_existent_id}", headers=headers)

        assert response.status_code == 204
        assert response.content == b""

    async def test_validation_error_invalid_uuid_format(
        self,
        http_client: AsyncClient,
        create_test_user,
        create_auth_token,
    ) -> None:
        user = await create_test_user(password="TestP@ss123!")
        token = await create_auth_token(user_id=user.id, role=UserRole.USER)
        headers = {"Authorization": f"Bearer {token}"}

        response = await http_client.delete("/api/v1/aliases/invalid-uuid-format", headers=headers)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)
