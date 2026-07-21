import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.anyio
class TestVerificationsRateLimits:
    async def test_rate_limit_for_create_verification(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
        test_email: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_VERIFICATION_CREATION.split("/")[0])
        payload = {"email": test_email, "action_type": "user_creation"}
        await rate_limit_checker(http_client, "POST", "/api/v1/verifications", limit, payload)

    async def test_rate_limit_for_confirm_verification(
        self,
        http_client: AsyncClient,
        rate_limit_checker,
        dummy_otp_code: str,
    ) -> None:
        limit = int(settings.RATE_LIMIT_VERIFICATION_CONFIRMATION.split("/")[0])
        payload = {"otp_code": dummy_otp_code}
        await rate_limit_checker(
            http_client,
            "PATCH",
            f"/api/v1/verifications/{uuid.uuid4()}",
            limit,
            payload,
        )
