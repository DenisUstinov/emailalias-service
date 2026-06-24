import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestUsersRateLimits:
    async def test_rate_limit_for_create_user(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_CREATION.split("/")[0])
        payload = {
            "email": "test@example.com",
            "password": "TestP@ss123!",
            "verification_token": "a" * 43,
        }
        await rate_limit_checker(http_client, "POST", "/api/v1/users", limit, payload)

    async def test_rate_limit_for_update_me(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_UPDATE.split("/")[0])
        headers = await authenticated_headers()
        payload = {"email": "new@example.com", "verification_token": "a" * 43}
        await rate_limit_checker(http_client, "PATCH", "/api/v1/users/me", limit, payload, headers)

    async def test_rate_limit_for_delete_me(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_DELETION.split("/")[0])
        headers = await authenticated_headers()
        payload = {"verification_token": "a" * 43}
        await rate_limit_checker(http_client, "DELETE", "/api/v1/users/me", limit, payload, headers)
