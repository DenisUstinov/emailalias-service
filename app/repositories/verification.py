from redis.asyncio import Redis

from app.schemas.verification import VerificationSessionData, VerificationTokenData


class VerificationRepository:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def increment_rate_limit(self, key: str, expire_seconds: int) -> int:
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, expire_seconds)
        return count

    async def get_session_id_by_contact_hash(self, contact_hash: str) -> str | None:
        index_key = f"verification:contact:{contact_hash}"
        return await self.redis.get(index_key)

    async def get_session_ttl(self, session_id: str) -> int:
        key = f"verification:{session_id}"
        return await self.redis.ttl(key)

    async def get_session(self, session_id: str) -> VerificationSessionData | None:
        key = f"verification:{session_id}"
        value = await self.redis.get(key)
        if value is None:
            return None
        return VerificationSessionData.model_validate_json(value)

    async def create_session(
        self, session_id: str, contact_hash: str, data: VerificationSessionData, expire_seconds: int
    ) -> None:
        session_key = f"verification:{session_id}"
        contact_key = f"verification:contact:{contact_hash}"
        pipe = self.redis.pipeline()
        await pipe.set(session_key, data.model_dump_json(), ex=expire_seconds)
        await pipe.set(contact_key, session_id, ex=expire_seconds)
        await pipe.execute()

    async def update_session(
        self, session_id: str, contact_hash: str, data: VerificationSessionData
    ) -> None:
        session_key = f"verification:{session_id}"
        contact_key = f"verification:contact:{contact_hash}"
        pipe = self.redis.pipeline()
        await pipe.set(session_key, data.model_dump_json(), keepttl=True)
        await pipe.set(contact_key, session_id, keepttl=True)
        await pipe.execute()

    async def delete_session(self, session_id: str, contact_hash: str) -> None:
        session_key = f"verification:{session_id}"
        contact_key = f"verification:contact:{contact_hash}"
        pipe = self.redis.pipeline()
        await pipe.delete(session_key)
        await pipe.delete(contact_key)
        await pipe.execute()

    async def save_token(
        self, token_hash: str, data: VerificationTokenData, expire_seconds: int
    ) -> None:
        key = f"vtoken:{token_hash}"
        await self.redis.set(key, data.model_dump_json(), ex=expire_seconds)

    async def get_token(self, token_hash: str) -> VerificationTokenData | None:
        key = f"vtoken:{token_hash}"
        value = await self.redis.get(key)
        if value is None:
            return None
        return VerificationTokenData.model_validate_json(value)

    async def delete_token(self, token_hash: str) -> None:
        key = f"vtoken:{token_hash}"
        await self.redis.delete(key)
