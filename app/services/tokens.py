import logging
import secrets
import uuid

from app.core.config import settings
from app.core.exceptions import InvalidCredentialsError, UserBannedError
from app.core.security import hash_token, verify_password
from app.repositories.tokens import TokenRepository
from app.repositories.users import UserRepository
from app.schemas.responses import TokenCreateResponse
from app.schemas.token import TokenData

logger = logging.getLogger(__name__)


class TokenService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def create_token(
        self,
        email: str,
        password: str,
    ) -> TokenCreateResponse:
        user = await self.user_repo.get_by_email(email)

        if not user:
            logger.warning(
                "Failed login attempt: user not found",
                extra={"email": email},
            )
            raise InvalidCredentialsError()

        if not verify_password(password, user.password_hash):
            logger.warning(
                "Failed login attempt: invalid password",
                extra={"email": email, "user_id": user.id},
            )
            raise InvalidCredentialsError()

        await self.revoke_active_tokens(user.id)

        if user.is_banned:
            logger.warning(
                "Login attempt by banned user",
                extra={"email": email, "user_id": user.id},
            )
            raise UserBannedError()

        raw_token = secrets.token_urlsafe(32)
        hashed_token = hash_token(raw_token)

        token_data = TokenData(
            user_id=user.id,
            role=user.role,
        )

        await self.token_repo.create(hashed_token, token_data, settings.TOKEN_TTL_SECONDS)

        logger.info(
            "Authentication successful",
            extra={"user_id": user.id, "email": email},
        )

        return TokenCreateResponse(
            access_token=raw_token,
            token_type="bearer",
            expires_in=settings.TOKEN_TTL_SECONDS,
        )

    async def revoke_active_tokens(self, user_id: uuid.UUID) -> None:
        existing_token = await self.token_repo.get_hashed_token_by_user_id(user_id)
        if existing_token:
            await self.token_repo.delete(existing_token)
            logger.info(
                "Active token revoked",
                extra={"user_id": user_id},
            )
