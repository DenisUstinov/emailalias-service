import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestPasswordsRateLimits:
    async def test_rate_limit_for_update_password(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
        test_email: str,
        valid_test_password: str,
        dummy_verification_token: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_PASSWORD_UPDATE.split("/")[0])
        payload = {
            "email": test_email,
            "new_password": valid_test_password,
            "verification_token": dummy_verification_token,
        }
        await rate_limit_checker(http_client, "PATCH", "/api/v1/passwords", limit, payload)
