from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import (
    ContactNotVerifiedError,
    VerificationAttemptsLimitExceededError,
    VerificationCooldownError,
    VerificationInvalidOTPError,
    VerificationMaxAttemptsExceededError,
    VerificationMaxRequestsExceededError,
    VerificationSessionNotFoundError,
)
from app.schemas.verification import (
    VerificationActionType,
    VerificationSessionData,
    VerificationTokenData,
)
from app.services.verifications import VerificationService
from tests.helpers import assert_exception_details


@pytest.mark.anyio
class TestVerificationServiceCreate:
    async def test_success_creates_new_session(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()
        repo_mock.get_session_id_by_contact_hash.return_value = None
        repo_mock.increment_rate_limit.return_value = 1

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            patch("app.services.verifications.secrets.randbelow", return_value=23456),
        ):
            result = await service.create_verification(
                "test@example.com", VerificationActionType.USER_CREATION
            )

        assert "verification_id" in result
        assert result["expires_in"] == settings.VERIFICATION_TTL_SECONDS
        repo_mock.create_session.assert_awaited_once()
        otp_sender_mock.send_otp.assert_awaited_once_with("test@example.com", "123456")

    async def test_success_resends_otp_updates_session(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        existing_session = VerificationSessionData(
            contact="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=0,
        )
        repo_mock.get_session_id_by_contact_hash.return_value = "sess_id"
        repo_mock.get_session_ttl.return_value = (
            settings.VERIFICATION_TTL_SECONDS - settings.VERIFICATION_COOLDOWN_SECONDS - 1
        )
        repo_mock.get_session.return_value = existing_session
        repo_mock.increment_rate_limit.return_value = 2

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            patch("app.services.verifications.secrets.randbelow", return_value=554321),
        ):
            await service.create_verification(
                "test@example.com", VerificationActionType.USER_CREATION
            )

        repo_mock.update_session.assert_awaited_once()
        updated_data = repo_mock.update_session.call_args[0][2]
        assert updated_data.request_count == 2
        assert updated_data.otp == "654321"

    async def test_raises_cooldown_when_not_elapsed(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()
        repo_mock.get_session_id_by_contact_hash.return_value = "sess_id"
        repo_mock.get_session_ttl.return_value = settings.VERIFICATION_TTL_SECONDS - 10

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            pytest.raises(VerificationCooldownError) as exc_info,
        ):
            await service.create_verification(
                "test@example.com", VerificationActionType.USER_CREATION
            )

        expected_remaining = settings.VERIFICATION_COOLDOWN_SECONDS - 10
        assert exc_info.value.status_code == 400
        assert (
            exc_info.value.detail
            == VerificationCooldownError(remaining_seconds=expected_remaining).detail
        )
        repo_mock.increment_rate_limit.assert_not_awaited()

    async def test_raises_max_attempts_exceeded_when_check_attempts_limit_reached(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        existing_session = VerificationSessionData(
            contact="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=settings.VERIFICATION_MAX_CHECK_ATTEMPTS,
        )
        repo_mock.get_session_id_by_contact_hash.return_value = "sess_id"
        repo_mock.get_session_ttl.return_value = (
            settings.VERIFICATION_TTL_SECONDS - settings.VERIFICATION_COOLDOWN_SECONDS - 1
        )
        repo_mock.get_session.return_value = existing_session

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            pytest.raises(VerificationMaxAttemptsExceededError) as exc_info,
        ):
            await service.create_verification(
                "test@example.com", VerificationActionType.USER_CREATION
            )

        assert_exception_details(exc_info, 400, VerificationMaxAttemptsExceededError)

    async def test_raises_max_requests_exceeded_when_rate_limit_reached(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()
        repo_mock.get_session_id_by_contact_hash.return_value = None
        repo_mock.increment_rate_limit.return_value = settings.VERIFICATION_MAX_REQUEST_COUNT + 1

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            pytest.raises(VerificationMaxRequestsExceededError) as exc_info,
        ):
            await service.create_verification(
                "test@example.com", VerificationActionType.USER_CREATION
            )

        assert_exception_details(exc_info, 400, VerificationMaxRequestsExceededError)


@pytest.mark.anyio
class TestVerificationServiceConfirm:
    async def test_success_confirms_otp_and_saves_token(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        session = VerificationSessionData(
            contact="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=0,
        )
        repo_mock.get_session.return_value = session

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            patch("app.services.verifications.secrets.token_urlsafe", return_value="raw_token"),
            patch("app.services.verifications.hash_token", return_value="hashed_token"),
        ):
            result = await service.confirm_verification("sess_id", "123456")

        assert result["verification_token"] == "raw_token"
        assert result["expires_in"] == settings.VERIFICATION_TOKEN_TTL_SECONDS
        repo_mock.delete_session.assert_awaited_once_with("sess_id", "hash")
        repo_mock.save_token.assert_awaited_once()

    async def test_raises_session_not_found_when_missing(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()
        repo_mock.get_session.return_value = None

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with pytest.raises(VerificationSessionNotFoundError) as exc_info:
            await service.confirm_verification("unknown", "123456")

        assert_exception_details(exc_info, 404, VerificationSessionNotFoundError)

    async def test_raises_attempts_limit_exceeded_when_check_attempts_reached(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        session = VerificationSessionData(
            contact="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=settings.VERIFICATION_MAX_CHECK_ATTEMPTS,
        )
        repo_mock.get_session.return_value = session

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with pytest.raises(VerificationAttemptsLimitExceededError) as exc_info:
            await service.confirm_verification("sess_id", "123456")

        assert_exception_details(exc_info, 400, VerificationAttemptsLimitExceededError)

    async def test_raises_invalid_otp_and_increments_attempts(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        session = VerificationSessionData(
            contact="test@example.com",
            otp="123456",
            action_type=VerificationActionType.USER_CREATION,
            request_count=1,
            check_attempts=0,
        )
        repo_mock.get_session.return_value = session

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_contact", return_value="hash"),
            pytest.raises(VerificationInvalidOTPError) as exc_info,
        ):
            await service.confirm_verification("sess_id", "000000")

        expected_remaining = settings.VERIFICATION_MAX_CHECK_ATTEMPTS - 1
        assert exc_info.value.status_code == 400
        assert (
            exc_info.value.detail
            == VerificationInvalidOTPError(attempts_remaining=expected_remaining).detail
        )
        repo_mock.update_session.assert_awaited_once()
        updated_data = repo_mock.update_session.call_args[0][2]
        assert updated_data.check_attempts == 1


@pytest.mark.anyio
class TestVerificationServiceVerifyOperationToken:
    async def test_success_verifies_and_deletes_token(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        token_data = VerificationTokenData(
            contact="test@example.com", action_type=VerificationActionType.USER_CREATION
        )
        repo_mock.get_token.return_value = token_data

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with patch("app.services.verifications.hash_token", return_value="hashed_token"):
            await service.verify_operation_token(
                "raw_token", "test@example.com", VerificationActionType.USER_CREATION
            )

        repo_mock.get_token.assert_awaited_once_with("hashed_token")
        repo_mock.delete_token.assert_awaited_once_with("hashed_token")

    async def test_raises_contact_not_verified_when_token_missing(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()
        repo_mock.get_token.return_value = None

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_token", return_value="hashed_token"),
            pytest.raises(ContactNotVerifiedError) as exc_info,
        ):
            await service.verify_operation_token(
                "raw_token", "test@example.com", VerificationActionType.USER_CREATION
            )

        assert_exception_details(exc_info, 400, ContactNotVerifiedError)

    async def test_raises_contact_not_verified_when_action_type_mismatch(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        token_data = VerificationTokenData(
            contact="test@example.com", action_type=VerificationActionType.PASSWORD_RESET
        )
        repo_mock.get_token.return_value = token_data

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_token", return_value="hashed_token"),
            pytest.raises(ContactNotVerifiedError) as exc_info,
        ):
            await service.verify_operation_token(
                "raw_token", "test@example.com", VerificationActionType.USER_CREATION
            )

        assert_exception_details(exc_info, 400, ContactNotVerifiedError)

    async def test_raises_contact_not_verified_when_contact_mismatch(self) -> None:
        repo_mock = AsyncMock()
        otp_sender_mock = AsyncMock()

        token_data = VerificationTokenData(
            contact="other@example.com", action_type=VerificationActionType.USER_CREATION
        )
        repo_mock.get_token.return_value = token_data

        service = VerificationService(verification_repo=repo_mock, otp_sender=otp_sender_mock)

        with (
            patch("app.services.verifications.hash_token", return_value="hashed_token"),
            pytest.raises(ContactNotVerifiedError) as exc_info,
        ):
            await service.verify_operation_token(
                "raw_token", "test@example.com", VerificationActionType.USER_CREATION
            )

        assert_exception_details(exc_info, 400, ContactNotVerifiedError)
