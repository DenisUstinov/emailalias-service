import pytest
from faker import Faker
from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import (
    VerificationAttemptsLimitExceededError,
    VerificationInvalidOTPError,
    VerificationSessionNotFoundError,
)
from app.core.security import hash_email, hash_token
from app.schemas.responses import VerificationConfirmResponse
from app.schemas.verification import (
    VerificationActionType,
    VerificationSessionData,
    VerificationTokenData,
)


@pytest.mark.anyio
class TestConfirmVerification:
    async def test_success_valid_otp_issues_token(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "44444444-4444-4444-4444-444444444444"
        action_type = VerificationActionType.USER_CREATION
        otp_code = "123456"

        await create_verification_session(email, verification_id, action_type, otp_code)

        payload = {"otp_code": otp_code}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 200
        data = VerificationConfirmResponse(**response.json())
        assert data.verification_token is not None
        assert len(data.verification_token) == 43
        assert isinstance(data.expires_in, int)

        stored_session = await redis_client.get(f"verification:{verification_id}")
        assert stored_session is None

        email_hash = hash_email(email)
        stored_email_key = await redis_client.get(f"verification:email:{email_hash}")
        assert stored_email_key is None

        token_hash = hash_token(data.verification_token)
        token_key = f"vtoken:{token_hash}"
        stored_token_data = await redis_client.get(token_key)
        assert stored_token_data is not None
        token_data = VerificationTokenData.model_validate_json(stored_token_data)
        assert token_data.email == email
        assert token_data.action_type == action_type

    async def test_idempotency_second_call_returns_not_found(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "99999999-9999-9999-9999-999999999999"
        action_type = VerificationActionType.EMAIL_CHANGE
        otp_code = "654321"

        await create_verification_session(email, verification_id, action_type, otp_code)

        payload = {"otp_code": otp_code}
        response_first = await http_client.patch(
            f"/api/v1/verifications/{verification_id}", json=payload
        )
        assert response_first.status_code == 200

        response_second = await http_client.patch(
            f"/api/v1/verifications/{verification_id}", json=payload
        )
        assert response_second.status_code == 404
        data = response_second.json()
        assert data["status"] == 404
        assert data["detail"] == VerificationSessionNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    @pytest.mark.parametrize(
        "payload",
        [
            {"otp_code": "12345"},
            {"otp_code": "1234567"},
            {"otp_code": "abcde"},
            {},
        ],
    )
    async def test_validation_errors_invalid_otp_format(
        self, http_client: AsyncClient, payload: dict
    ) -> None:
        verification_id = "55555555-5555-5555-5555-555555555555"
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_business_error_session_not_found(
        self, http_client: AsyncClient, faker: Faker
    ) -> None:
        verification_id = "66666666-6666-6666-6666-666666666666"
        payload = {"otp_code": "123456"}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404
        assert data["detail"] == VerificationSessionNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_invalid_otp_increments_counter(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "77777777-7777-7777-7777-777777777777"
        action_type = VerificationActionType.PASSWORD_RESET

        await create_verification_session(email, verification_id, action_type, "123456")

        payload = {"otp_code": "000000"}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 400
        data = response.json()
        expected_attempts = settings.VERIFICATION_MAX_CHECK_ATTEMPTS - 1
        assert data["status"] == 400
        assert (
            data["detail"]
            == VerificationInvalidOTPError(attempts_remaining=expected_attempts).detail
        )
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

        stored_session = await redis_client.get(f"verification:{verification_id}")
        updated_session = VerificationSessionData.model_validate_json(stored_session)
        assert updated_session.check_attempts == 1

        token_hash = hash_token("any_token")
        token_key = f"vtoken:{token_hash}"
        stored_token = await redis_client.get(token_key)
        assert stored_token is None

    async def test_business_error_attempts_limit_exceeded(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "88888888-8888-8888-8888-888888888888"
        action_type = VerificationActionType.EMAIL_CHANGE

        await create_verification_session(
            email,
            verification_id,
            action_type,
            "123456",
            check_attempts=settings.VERIFICATION_MAX_CHECK_ATTEMPTS,
        )

        payload = {"otp_code": "000000"}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400
        assert data["detail"] == VerificationAttemptsLimitExceededError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_session_ttl_expired_before_confirm(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        action_type = VerificationActionType.USER_CREATION
        otp_code = "111111"

        await create_verification_session(email, verification_id, action_type, otp_code, ttl=1)

        session_key = f"verification:{verification_id}"
        email_hash = hash_email(email)
        email_key = f"verification:email:{email_hash}"
        await redis_client.expire(session_key, 0)
        await redis_client.expire(email_key, 0)

        payload = {"otp_code": otp_code}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404
        assert data["detail"] == VerificationSessionNotFoundError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_failed_attempt_does_not_create_verification_token(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        action_type = VerificationActionType.USER_DELETION

        await create_verification_session(email, verification_id, action_type, "999999")

        payload = {"otp_code": "000000"}
        response = await http_client.patch(f"/api/v1/verifications/{verification_id}", json=payload)

        assert response.status_code == 400
        data = response.json()
        expected_attempts = settings.VERIFICATION_MAX_CHECK_ATTEMPTS - 1
        assert data["status"] == 400
        assert (
            data["detail"]
            == VerificationInvalidOTPError(attempts_remaining=expected_attempts).detail
        )
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

        for test_token in ["test1", "test2", "wrong"]:
            token_hash = hash_token(test_token)
            token_key = f"vtoken:{token_hash}"
            stored = await redis_client.get(token_key)
            assert stored is None
