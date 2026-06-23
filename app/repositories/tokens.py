from uuid import UUID

from redis.asyncio import Redis

from app.schemas.token import TokenData


class TokenRepository:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def create(self, hashed_token: str, data: TokenData, expire_seconds: int) -> None:
        hashed_token_key = f"tkn:{hashed_token}"
        user_key = f"usr:{data.user_id}"
        pipe = self.redis.pipeline()
        await pipe.set(hashed_token_key, data.model_dump_json(), ex=expire_seconds)
        await pipe.set(user_key, hashed_token, ex=expire_seconds)
        await pipe.execute()

    async def get(self, hashed_token: str) -> TokenData | None:
        value = await self.redis.get(f"tkn:{hashed_token}")
        if value is None:
            return None
        return TokenData.model_validate_json(value)

    async def delete(self, hashed_token: str) -> None:
        hashed_token_key = f"tkn:{hashed_token}"
        value = await self.redis.get(hashed_token_key)
        if value:
            data = TokenData.model_validate_json(value)
            user_key = f"usr:{data.user_id}"
            pipe = self.redis.pipeline()
            await pipe.delete(hashed_token_key)
            await pipe.delete(user_key)
            await pipe.execute()

    async def get_hashed_token_by_user_id(self, user_id: UUID) -> str | None:
        return await self.redis.get(f"usr:{user_id}")
