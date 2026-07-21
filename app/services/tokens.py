import logging
import secrets
from datetime import UTC, datetime, timedelta

from app.core.exceptions import (
    InvalidCredentialsError,
    TokenPasswordAttemptsBlockedError,
    UserBannedError,
)
from app.core.security import hash_contact, hash_token, verify_password
from app.repositories.tokens import PasswordAttemptSessionRepository, TokenRepository
from app.repositories.users import UserRepository
from app.schemas.responses import TokenCreateResponse
from app.schemas.tokens import PasswordAttemptSessionData

logger = logging.getLogger(__name__)


class TokenService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
        password_attempt_repo: PasswordAttemptSessionRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.password_attempt_repo = password_attempt_repo

    async def create_token(
        self,
        email: str,
        password: str,
    ) -> TokenCreateResponse:
        email_hash = hash_contact(email)

        session = await self.password_attempt_repo.get_session(email_hash)
        if session and session.blocked_until and session.blocked_until > datetime.now(UTC):
            remaining_seconds = int((session.blocked_until - datetime.now(UTC)).total_seconds())
            raise TokenPasswordAttemptsBlockedError(remaining_seconds=remaining_seconds)

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
            await self._handle_failed_attempt(email_hash, session)
            raise InvalidCredentialsError()

        if user.is_banned:
            logger.warning(
                "Login attempt by banned user",
                extra={"email": email, "user_id": user.id},
            )
            raise UserBannedError()

        await self.password_attempt_repo.delete_session(email_hash)

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

    async def _handle_failed_attempt(
        self,
        email_hash: str,
        existing_session: PasswordAttemptSessionData | None,
    ) -> None:
        now = datetime.now(UTC)

        if existing_session:
            window_start = existing_session.window_start
            failed_attempts = existing_session.failed_attempts
            last_block_ts = existing_session.last_block_ts
        else:
            window_start = now
            failed_attempts = 0
            last_block_ts = None

        if (now - window_start).total_seconds() > 3600:
            window_start = now
            failed_attempts = 0

        failed_attempts += 1

        blocked_until = None
        if failed_attempts >= 3:
            if last_block_ts is None or (now - last_block_ts).total_seconds() > 3600:
                blocked_until = now + timedelta(minutes=15)
            else:
                blocked_until = now + timedelta(hours=1)
            last_block_ts = now

        new_session = PasswordAttemptSessionData(
            failed_attempts=failed_attempts,
            window_start=window_start,
            blocked_until=blocked_until,
            last_block_ts=last_block_ts,
        )

        expire_seconds = 3600
        await self.password_attempt_repo.save_session(email_hash, new_session, expire_seconds)
