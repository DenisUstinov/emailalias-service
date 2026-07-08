import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import UserNotFoundError
from app.models.domain import User, UserRole
from app.schemas.responses import UserAdminUpdateResponse


@pytest.mark.anyio
class TestUpdateUserAdmin:
    async def test_success_update_role_and_ban_status(
        self,
        http_client: AsyncClient,
        db_session,
        authenticated_headers,
        create_test_user,
        generate_test_email,
        valid_test_password,
    ) -> None:
        target_email = generate_test_email(prefix="admin")
        target_user = await create_test_user(email=target_email, password=valid_test_password)
        admin_headers = await authenticated_headers(role=UserRole.ADMIN)

        payload = {"is_banned": True, "role": UserRole.ADMIN.value}
        response = await http_client.patch(
            f"/api/v1/users/{target_user.id}", json=payload, headers=admin_headers
        )

        assert response.status_code == 200
        data = UserAdminUpdateResponse(**response.json())
        assert data.is_banned is True
        assert data.role == UserRole.ADMIN.value
        assert data.updated_at is not None

        result = await db_session.execute(
            select(User).where(User.id == target_user.id).execution_options(populate_existing=True)
        )
        updated_user = result.scalar_one()
        assert updated_user.is_banned is True
        assert updated_user.role == UserRole.ADMIN

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"is_banned": "not-a-bool"},
            {"role": "invalid_role"},
            {"is_banned": True, "role": 123},
        ],
    )
    async def test_validation_errors(
        self,
        http_client: AsyncClient,
        payload: dict,
        authenticated_headers,
    ) -> None:
        admin_headers = await authenticated_headers(role=UserRole.ADMIN)
        non_existent_id = uuid.uuid4()

        response = await http_client.patch(
            f"/api/v1/users/{non_existent_id}", json=payload, headers=admin_headers
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

    async def test_auth_error_unauthorized(
        self,
        http_client: AsyncClient,
        create_test_user,
        generate_test_email,
        valid_test_password,
    ) -> None:
        target_email = generate_test_email(prefix="admin")
        target_user = await create_test_user(email=target_email, password=valid_test_password)

        payload = {"is_banned": True}
        response = await http_client.patch(f"/api/v1/users/{target_user.id}", json=payload)

        assert response.status_code == 401
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 401
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)

    async def test_auth_error_non_admin(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        create_test_user,
        generate_test_email,
        valid_test_password,
    ) -> None:
        target_email = generate_test_email(prefix="admin")
        target_user = await create_test_user(email=target_email, password=valid_test_password)
        user_headers = await authenticated_headers(role=UserRole.USER)

        payload = {"is_banned": True}
        response = await http_client.patch(
            f"/api/v1/users/{target_user.id}", json=payload, headers=user_headers
        )

        assert response.status_code == 403
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 403
        assert isinstance(data["detail"], str)
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_user_not_found(
        self,
        http_client: AsyncClient,
        authenticated_headers,
    ) -> None:
        admin_headers = await authenticated_headers(role=UserRole.ADMIN)
        non_existent_id = uuid.uuid4()

        payload = {"is_banned": True}
        response = await http_client.patch(
            f"/api/v1/users/{non_existent_id}", json=payload, headers=admin_headers
        )

        assert response.status_code == 404
        data = response.json()
        assert isinstance(data["status"], int)
        assert data["status"] == 404
        assert data["detail"] == UserNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)
