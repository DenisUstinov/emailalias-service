import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestUsersRateLimits:
    async def test_rate_limit_for_create_user(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
        test_email: str,
        valid_test_password: str,
        dummy_verification_token: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_CREATION.split("/")[0])
        payload = {
            "email": test_email,
            "password": valid_test_password,
            "verification_token": dummy_verification_token,
        }
        await rate_limit_checker(http_client, "POST", "/api/v1/users", limit, payload)

    async def test_rate_limit_for_update_me(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
        test_email_alt: str,
        dummy_verification_token: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_UPDATE.split("/")[0])
        headers = await authenticated_headers()
        payload = {"email": test_email_alt, "verification_token": dummy_verification_token}
        await rate_limit_checker(http_client, "PATCH", "/api/v1/users/me", limit, payload, headers)

    async def test_rate_limit_for_delete_me(
        self,
        http_client: AsyncClient,
        authenticated_headers,
        rate_limit_checker,
        dummy_verification_token: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_USER_DELETION.split("/")[0])
        headers = await authenticated_headers()
        payload = {"verification_token": dummy_verification_token}
        await rate_limit_checker(http_client, "DELETE", "/api/v1/users/me", limit, payload, headers)
