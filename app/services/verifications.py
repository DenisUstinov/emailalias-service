import logging
import secrets
import uuid

from app.core.config import settings
from app.core.exceptions import (
    EmailNotVerifiedError,
    VerificationAttemptsLimitExceededError,
    VerificationCooldownError,
    VerificationInvalidOTPError,
    VerificationMaxAttemptsExceededError,
    VerificationMaxRequestsExceededError,
    VerificationSessionNotFoundError,
)
from app.core.notifications import EmailSender
from app.core.security import hash_email, hash_token
from app.repositories.verification import VerificationRepository
from app.schemas.verification import (
    VerificationActionType,
    VerificationSessionData,
    VerificationTokenData,
)

logger = logging.getLogger(__name__)


class VerificationService:
    def __init__(
        self, verification_repo: VerificationRepository, email_sender: EmailSender
    ) -> None:
        self.verification_repo = verification_repo
        self.email_sender = email_sender

    async def create_verification(
        self, email: str, action_type: VerificationActionType
    ) -> dict[str, str | int]:
        email_hash = hash_email(email)
        session_id = await self.verification_repo.get_session_id_by_email_hash(email_hash)

        existing_session = None
        if session_id:
            current_ttl = await self.verification_repo.get_session_ttl(session_id)
            if current_ttl > 0:
                elapsed = settings.VERIFICATION_TTL_SECONDS - current_ttl
                if elapsed < settings.VERIFICATION_COOLDOWN_SECONDS:
                    remaining = settings.VERIFICATION_COOLDOWN_SECONDS - elapsed
                    logger.warning(
                        "Verification blocked: cooldown not elapsed",
                        extra={"email": email, "remaining_seconds": remaining},
                    )
                    raise VerificationCooldownError(remaining)

            existing_session = await self.verification_repo.get_session(session_id)
            if (
                existing_session
                and existing_session.check_attempts >= settings.VERIFICATION_MAX_CHECK_ATTEMPTS
            ):
                logger.warning(
                    "Verification blocked: max check attempts exceeded",
                    extra={"email": email, "attempts": existing_session.check_attempts},
                )
                raise VerificationMaxAttemptsExceededError()

        rate_limit_key = f"rate_limit:otp:{email_hash}"
        count = await self.verification_repo.increment_rate_limit(
            rate_limit_key, settings.OTP_RATE_LIMIT_TTL_SECONDS
        )
        if count > settings.VERIFICATION_MAX_REQUEST_COUNT:
            logger.warning(
                "Verification blocked: rate limit exceeded",
                extra={"email": email, "count": count},
            )
            raise VerificationMaxRequestsExceededError()

        otp = self._generate_otp()

        if existing_session:
            updated_session = VerificationSessionData(
                email=email,
                otp=otp,
                action_type=action_type,
                request_count=existing_session.request_count + 1,
                check_attempts=existing_session.check_attempts,
            )
            await self.verification_repo.update_session(session_id, email_hash, updated_session)
        else:
            session_id = str(uuid.uuid4())
            initial_session = VerificationSessionData(
                email=email,
                otp=otp,
                action_type=action_type,
                request_count=1,
                check_attempts=0,
            )
            await self.verification_repo.create_session(
                session_id, email_hash, initial_session, settings.VERIFICATION_TTL_SECONDS
            )

        await self.email_sender.send_otp(email, otp)
        logger.info(
            "OTP sent successfully",
            extra={
                "email": email,
                "is_resend": bool(existing_session),
                "verification_id": session_id,
            },
        )
        return {"verification_id": session_id, "expires_in": settings.VERIFICATION_TTL_SECONDS}

    async def confirm_verification(
        self, verification_id: str, otp_code: str
    ) -> dict[str, str | int]:
        session = await self.verification_repo.get_session(verification_id)
        if session is None:
            logger.warning(
                "Verification session not found or expired",
                extra={"verification_id": verification_id},
            )
            raise VerificationSessionNotFoundError()

        if session.check_attempts >= settings.VERIFICATION_MAX_CHECK_ATTEMPTS:
            logger.warning(
                "Verification blocked: max check attempts exceeded",
                extra={"verification_id": verification_id, "attempts": session.check_attempts},
            )
            raise VerificationAttemptsLimitExceededError()

        email_hash = hash_email(session.email)

        # TODO: Хэшировать ОТП код
        if otp_code != session.otp:
            updated_session = VerificationSessionData(
                email=session.email,
                otp=session.otp,
                action_type=session.action_type,
                request_count=session.request_count,
                check_attempts=session.check_attempts + 1,
            )
            await self.verification_repo.update_session(
                verification_id, email_hash, updated_session
            )
            remaining = settings.VERIFICATION_MAX_CHECK_ATTEMPTS - updated_session.check_attempts
            logger.warning(
                "Invalid OTP provided",
                extra={
                    "verification_id": verification_id,
                    "attempts_used": updated_session.check_attempts,
                    "attempts_remaining": remaining,
                },
            )
            raise VerificationInvalidOTPError(attempts_remaining=remaining)

        await self.verification_repo.delete_session(verification_id, email_hash)

        raw_token = secrets.token_urlsafe(32)
        hashed_token = hash_token(raw_token)
        token_data = VerificationTokenData(email=session.email, action_type=session.action_type)
        await self.verification_repo.save_token(
            hashed_token, token_data, settings.VERIFICATION_TOKEN_TTL_SECONDS
        )

        logger.info(
            "Email successfully verified and token issued",
            extra={"email": session.email, "action_type": session.action_type},
        )
        return {
            "verification_token": raw_token,
            "expires_in": settings.VERIFICATION_TOKEN_TTL_SECONDS,
        }

    @staticmethod
    def _generate_otp() -> str:
        return f"{secrets.randbelow(900000) + 100000:06d}"

    async def verify_operation_token(
        self, token: str, email: str, expected_action: VerificationActionType
    ) -> None:
        token_hash = hash_token(token)
        token_data = await self.verification_repo.get_token(token_hash)

        if token_data is None:
            logger.warning(
                "Verification token not found or expired",
                extra={"email": email, "action_type": expected_action.value},
            )
            raise EmailNotVerifiedError()

        if token_data.action_type != expected_action:
            logger.warning(
                "Verification token action type mismatch",
                extra={
                    "email": email,
                    "expected_action": expected_action.value,
                    "actual_action": token_data.action_type.value,
                },
            )
            raise EmailNotVerifiedError()

        if token_data.email != email:
            logger.warning(
                "Verification token email mismatch",
                extra={
                    "provided_email": email,
                    "token_email": token_data.email,
                },
            )
            raise EmailNotVerifiedError()

        await self.verification_repo.delete_token(token_hash)
