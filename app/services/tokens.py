import logging
import secrets

from app.core.exceptions import InvalidCredentialsError, UserBannedError
from app.core.security import hash_token, verify_password
from app.repositories.tokens import TokenRepository
from app.repositories.users import UserRepository
from app.schemas.responses import TokenCreateResponse

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
        user = await self.user_repo.get_by_email_for_update(email)

        if not user:
            logger.warning(
                "Failed login attempt: user not found",
                extra={"email": email},
            )
            raise InvalidCredentialsError()

        if not verify_password(user.password_hash, password):
            logger.warning(
                "Failed login attempt: invalid password",
                extra={"email": email, "user_id": user.id},
            )
            raise InvalidCredentialsError()

        if user.is_banned:
            logger.warning(
                "Login attempt by banned user",
                extra={"email": email, "user_id": user.id},
            )
            raise UserBannedError()

        await self.token_repo.revoke_all_by_user_id(user.id)

        raw_token = secrets.token_urlsafe(32)
        hashed_token = hash_token(raw_token)

        await self.token_repo.create(hashed_token=hashed_token, user_id=user.id)

        logger.info(
            "Authentication successful",
            extra={"user_id": user.id, "email": email},
        )

        return TokenCreateResponse(
            access_token=raw_token,
            token_type="bearer",
        )
