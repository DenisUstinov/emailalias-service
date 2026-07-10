import uuid

from sqlalchemy import func, select, update

from app.models.domain import Token


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
