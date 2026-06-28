from collections.abc import Awaitable, Callable

import pytest
from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import hash_contact
from app.schemas.verification import VerificationActionType, VerificationSessionData


@pytest.fixture
def create_verification_session(
    redis_client: Redis,
) -> Callable[..., Awaitable[None]]:
    async def _create(
        contact: str,
        verification_id: str,
        action_type: VerificationActionType,
        otp_code: str,
        request_count: int = 1,
        check_attempts: int = 0,
        ttl: int | None = None,
    ) -> None:
        ttl = ttl if ttl is not None else settings.VERIFICATION_TTL_SECONDS
        contact_hash = hash_contact(contact)
        session = VerificationSessionData(
            contact=contact,
            otp=otp_code,
            action_type=action_type,
            request_count=request_count,
            check_attempts=check_attempts,
        )
        session_key = f"verification:{verification_id}"
        contact_key = f"verification:contact:{contact_hash}"
        await redis_client.set(session_key, session.model_dump_json(), ex=ttl)
        await redis_client.set(contact_key, verification_id, ex=ttl)

    return _create
