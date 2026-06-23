import asyncio
import logging

from app.core.exceptions import (
    UserBannedError,
    UserNotFoundError,
)
from app.core.security import hash_password
from app.repositories.users import UserRepository
from app.schemas.requests import PasswordUpdateRequest
from app.schemas.verification import VerificationActionType
from app.services.tokens import TokenService
from app.services.verifications import VerificationService

logger = logging.getLogger(__name__)


class PasswordService:
    def __init__(
        self,
        user_repo: UserRepository,
        verification_service: VerificationService,
        token_service: TokenService,
    ) -> None:
        self.user_repo = user_repo
        self.verification_service = verification_service
        self.token_service = token_service

    async def update_password(self, request: PasswordUpdateRequest) -> None:
        await self.verification_service.verify_operation_token(
            token=request.verification_token,
            email=request.email,
            expected_action=VerificationActionType.PASSWORD_RESET,
        )

        user = await self.user_repo.get_by_email_for_update(request.email)
        if not user:
            logger.warning(
                "Password update attempt for non-existent user",
                extra={"email": request.email},
            )
            raise UserNotFoundError()

        if user.is_banned:
            logger.warning(
                "Password update attempt for banned user",
                extra={"email": request.email},
            )
            raise UserBannedError()

        password_hash = await asyncio.to_thread(hash_password, request.new_password)
        await self.user_repo.update(user_id=user.id, password_hash=password_hash)

        try:
            await self.token_service.revoke_active_tokens(user.id)
        except Exception as e:
            logger.error(
                "Failed to execute post-commit side effects on password update",
                extra={"email": request.email, "user_id": user.id, "error": str(e)},
            )

        logger.info(
            "Password successfully updated",
            extra={"user_id": user.id, "email": user.email},
        )
