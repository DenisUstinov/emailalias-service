import uuid

from redis.asyncio import Redis
from sqlalchemy import func, select, update

from app.models.domain import Token
from app.schemas.tokens import PasswordAttemptSessionData


class TokenRepository:
    def __init__(self, session) -> None:
        self.session = session

    async def create(self, hashed_token: str, user_id: uuid.UUID) -> None:
        token = Token(token_hash=hashed_token, user_id=user_id)
        self.session.add(token)
        await self.session.flush()

    async def get(self, hashed_token: str) -> Token | None:
        stmt = select(Token).where(
            Token.token_hash == hashed_token,
            Token.is_active,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_all_by_user_id(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(Token).where(Token.user_id == user_id, Token.is_active).values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def touch(self, token_id: uuid.UUID) -> None:
        stmt = update(Token).where(Token.id == token_id).values(last_used_at=func.now())
        await self.session.execute(stmt)
        await self.session.flush()


class PasswordAttemptSessionRepository:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_session(self, email_hash: str) -> PasswordAttemptSessionData | None:
        key = f"password_attempts:{email_hash}"
        value = await self.redis.get(key)
        if value is None:
            return None
        return PasswordAttemptSessionData.model_validate_json(value)

    async def save_session(
        self, email_hash: str, data: PasswordAttemptSessionData, expire_seconds: int
    ) -> None:
        key = f"password_attempts:{email_hash}"
        await self.redis.set(key, data.model_dump_json(), ex=expire_seconds)

    async def delete_session(self, email_hash: str) -> None:
        key = f"password_attempts:{email_hash}"
        await self.redis.delete(key)
