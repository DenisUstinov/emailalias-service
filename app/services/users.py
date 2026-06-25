import asyncio
import logging
import uuid

from sqlalchemy.exc import IntegrityError, NoResultFound

from app.core.exceptions import (
    CurrentPasswordInvalidError,
    CurrentPasswordRequiredError,
    EmailAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
)
from app.core.security import hash_password, verify_password
from app.models.domain import User, UserRole
from app.repositories.users import UserRepository
from app.schemas.requests import UserCreateRequest
from app.schemas.responses import UserAdminUpdateResponse, UserCreateResponse, UserUpdateResponse
from app.schemas.verification import VerificationActionType
from app.services.tokens import TokenService
from app.services.verifications import VerificationService

logger = logging.getLogger(__name__)


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        verification_service: VerificationService,
        token_service: TokenService,
    ) -> None:
        self.user_repo = user_repo
        self.verification_service = verification_service
        self.token_service = token_service

    async def _get_active_user(self, user_id: uuid.UUID) -> User | None:
        user = await self.user_repo.get_by_id_for_update(user_id)
        if not user:
            return None
        if user.is_banned:
            logger.error(
                "Operation attempt by banned user with active session",
                extra={"user_id": user_id},
            )
            try:
                await self.token_service.revoke_active_tokens(user_id)
            except Exception as e:
                logger.error(
                    "Failed to revoke tokens for banned user",
                    extra={"user_id": user_id, "error": str(e)},
                )
            raise UserBannedError()
        return user

    async def create_user(self, request: UserCreateRequest) -> UserCreateResponse:
        await self.verification_service.verify_operation_token(
            token=request.verification_token,
            email=request.email,
            expected_action=VerificationActionType.USER_CREATION,
        )

        existing_user = await self.user_repo.get_by_email_including_deleted_for_update(
            request.email
        )

        password_hash = await asyncio.to_thread(hash_password, request.password)

        if existing_user:
            if existing_user.is_banned:
                logger.warning(
                    "Registration attempt for banned user",
                    extra={"email": request.email},
                )
                raise UserBannedError()

            if existing_user.deleted_at is None:
                logger.warning(
                    "Registration attempt for already active user",
                    extra={"email": request.email},
                )
                raise EmailAlreadyExistsError()

            created = await self.user_repo.reactivate(
                user_id=existing_user.id,
                password_hash=password_hash,
            )
        else:
            new_user = User(email=request.email, password_hash=password_hash)
            created = await self.user_repo.create(new_user)

        logger.info(
            "User successfully registered or reactivated",
            extra={"user_id": created.id, "email": created.email},
        )
        return UserCreateResponse.model_validate(created)

    async def delete_user(self, user_id: uuid.UUID, verification_token: str) -> None:
        user = await self._get_active_user(user_id)

        if user:
            await self.verification_service.verify_operation_token(
                token=verification_token,
                email=user.email,
                expected_action=VerificationActionType.USER_DELETION,
            )
            await self.user_repo.delete(user_id)

            logger.info(
                "User account successfully soft-deleted",
                extra={"user_id": user_id},
            )
        else:
            logger.error(
                "Deletion attempt for non-existent user with active session",
                extra={"user_id": user_id},
            )

        try:
            await self.token_service.revoke_active_tokens(user_id)
        except Exception as e:
            logger.error(
                "Failed to revoke active tokens during user deletion",
                extra={"user_id": user_id, "error": str(e)},
            )

    async def update_user(
        self,
        user_id: uuid.UUID,
        email: str | None = None,
        new_password: str | None = None,
        current_password: str | None = None,
        verification_token: str | None = None,
    ) -> UserUpdateResponse:
        user = await self._get_active_user(user_id)
        if not user:
            logger.error(
                "Update attempt for non-existent user with active session",
                extra={"user_id": user_id},
            )
            try:
                await self.token_service.revoke_active_tokens(user_id)
            except Exception as e:
                logger.error(
                    "Failed to revoke tokens for non-existent user",
                    extra={"user_id": user_id, "error": str(e)},
                )
            raise UserNotFoundError()

        if new_password is not None:
            if current_password is None:
                logger.warning(
                    "Password change attempt without current password",
                    extra={"user_id": user_id},
                )
                raise CurrentPasswordRequiredError()

            if not verify_password(current_password, user.password_hash):
                logger.warning(
                    "Invalid current password provided",
                    extra={"user_id": user_id},
                )
                raise CurrentPasswordInvalidError()

            new_password_hash = await asyncio.to_thread(hash_password, new_password)
        else:
            new_password_hash = None

        if email is not None:
            await self.verification_service.verify_operation_token(
                token=verification_token,
                email=email,
                expected_action=VerificationActionType.EMAIL_CHANGE,
            )

        try:
            updated = await self.user_repo.update(
                user_id=user_id,
                email=email,
                password_hash=new_password_hash,
            )
        except IntegrityError as exc:
            logger.error(
                "Database integrity error during user update",
                extra={"user_id": user_id, "email": email, "db_error": str(exc.orig)},
            )
            raise EmailAlreadyExistsError() from None

        try:
            await self.token_service.revoke_active_tokens(user_id)
        except Exception as e:
            logger.error(
                "Failed to execute post-flush side effects on user update",
                extra={"user_id": user_id, "error": str(e)},
            )

        logger.info(
            "User successfully updated",
            extra={"user_id": updated.id, "email": updated.email},
        )
        return UserUpdateResponse.model_validate(updated)

    async def update_user_admin(
        self,
        user_id: uuid.UUID,
        is_banned: bool | None = None,
        role: UserRole | None = None,
    ) -> UserAdminUpdateResponse:
        user = await self.user_repo.get_by_id_for_update(user_id)
        if not user:
            logger.warning(
                "User not found for admin update",
                extra={"user_id": user_id},
            )
            raise UserNotFoundError()

        try:
            updated = await self.user_repo.update(
                user_id=user_id,
                is_banned=is_banned,
                role=role,
            )
        except NoResultFound:
            logger.warning(
                "User not found for admin update",
                extra={"user_id": user_id},
            )
            raise UserNotFoundError() from None

        try:
            await self.token_service.revoke_active_tokens(user_id)
        except Exception as e:
            logger.error(
                "Failed to execute post-flush side effects on admin user update",
                extra={"user_id": user_id, "error": str(e)},
            )

        logger.info(
            "User successfully updated by admin",
            extra={
                "user_id": updated.id,
                "is_banned": updated.is_banned,
                "role": updated.role.value,
            },
        )
        return UserAdminUpdateResponse.model_validate(updated)
