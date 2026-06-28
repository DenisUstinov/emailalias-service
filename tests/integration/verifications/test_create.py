import pytest
from faker import Faker
from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import (
    VerificationCooldownError,
    VerificationMaxRequestsExceededError,
)
from app.core.security import hash_contact
from app.schemas.responses import VerificationCreateResponse
from app.schemas.verification import VerificationActionType, VerificationSessionData


@pytest.mark.anyio
class TestCreateVerification:
    async def test_success_creates_new_session(
        self,
        http_client: AsyncClient,
        redis_client,
        faker: Faker,
        override_otp_sender,
    ) -> None:
        email = faker.email().lower()
        action_type = VerificationActionType.USER_CREATION
        payload = {"email": email, "action_type": action_type.value}

        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 200
        data = VerificationCreateResponse(**response.json())
        verification_id = data.verification_id

        session_key = f"verification:{verification_id}"
        stored_session = await redis_client.get(session_key)
        assert stored_session is not None
        session = VerificationSessionData.model_validate_json(stored_session)
        assert session.contact == email
        assert session.action_type == action_type
        assert len(session.otp) == 6
        assert session.request_count == 1
        assert session.check_attempts == 0

        contact_hash = hash_contact(email)
        contact_key = f"verification:contact:{contact_hash}"
        stored_id = await redis_client.get(contact_key)
        assert stored_id == str(verification_id)

        rate_limit_key = f"rate_limit:otp:{contact_hash}"
        rate_limit_count = await redis_client.get(rate_limit_key)
        assert rate_limit_count == "1"

        override_otp_sender.send_otp.assert_awaited_once_with(email, session.otp)

    async def test_success_resend_after_cooldown_elapsed(
        self,
        http_client: AsyncClient,
        redis_client,
        faker: Faker,
        override_otp_sender,
        create_verification_session,
    ) -> None:
        email = faker.email().lower()
        verification_id = "11111111-1111-1111-1111-111111111111"
        action_type = VerificationActionType.PASSWORD_RESET

        await create_verification_session(email, verification_id, action_type, "123456")

        ttl_after_cooldown = (
            settings.VERIFICATION_TTL_SECONDS - settings.VERIFICATION_COOLDOWN_SECONDS - 1
        )
        session_key = f"verification:{verification_id}"
        contact_hash = hash_contact(email)
        contact_key = f"verification:contact:{contact_hash}"
        await redis_client.expire(session_key, ttl_after_cooldown)
        await redis_client.expire(contact_key, ttl_after_cooldown)

        payload = {"email": email, "action_type": action_type.value}
        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 200
        data = VerificationCreateResponse(**response.json())
        assert str(data.verification_id) == verification_id

        stored_session = await redis_client.get(session_key)
        updated_session = VerificationSessionData.model_validate_json(stored_session)
        assert updated_session.request_count == 2
        assert updated_session.check_attempts == 0
        assert updated_session.otp != "123456"

        override_otp_sender.send_otp.assert_awaited_once_with(email, updated_session.otp)

    async def test_success_creates_new_session_after_ttl_expired(
        self,
        http_client: AsyncClient,
        redis_client,
        faker: Faker,
        override_otp_sender,
        create_verification_session,
    ) -> None:
        email = faker.email().lower()
        old_verification_id = "22222222-2222-2222-2222-222222222222"
        action_type = VerificationActionType.EMAIL_CHANGE

        await create_verification_session(
            email,
            old_verification_id,
            action_type,
            "654321",
            request_count=3,
            check_attempts=1,
            ttl=1,
        )

        session_key = f"verification:{old_verification_id}"
        contact_hash = hash_contact(email)
        contact_key = f"verification:contact:{contact_hash}"
        await redis_client.expire(session_key, 0)
        await redis_client.expire(contact_key, 0)

        payload = {"email": email, "action_type": action_type.value}
        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 200
        data = VerificationCreateResponse(**response.json())
        assert data.verification_id != old_verification_id

        new_session_key = f"verification:{data.verification_id}"
        stored_session = await redis_client.get(new_session_key)
        new_session = VerificationSessionData.model_validate_json(stored_session)
        assert new_session.request_count == 1
        assert new_session.otp != "654321"
        assert new_session.check_attempts == 0

        override_otp_sender.send_otp.assert_awaited_once_with(email, new_session.otp)

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": "invalid", "action_type": "user_creation"},
            {"email": "test@", "action_type": "user_creation"},
            {"email": "", "action_type": "user_creation"},
            {"action_type": "user_creation"},
            {"email": "test@example.com"},
            {"email": "test@example.com", "action_type": "invalid_action"},
        ],
    )
    async def test_validation_errors_invalid_payload(
        self, http_client: AsyncClient, payload: dict
    ) -> None:
        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], int)
        assert data["status"] == 422
        assert isinstance(data["detail"], str)
        assert isinstance(data["instance"], str)
        assert isinstance(data["field_errors"], list)

    async def test_business_error_cooldown_not_elapsed(
        self, http_client: AsyncClient, redis_client, faker: Faker, create_verification_session
    ) -> None:
        email = faker.email().lower()
        verification_id = "33333333-3333-3333-3333-333333333333"
        action_type = VerificationActionType.USER_DELETION

        await create_verification_session(email, verification_id, action_type, "111222")

        ttl_during_cooldown = settings.VERIFICATION_TTL_SECONDS - 10
        session_key = f"verification:{verification_id}"
        contact_hash = hash_contact(email)
        contact_key = f"verification:contact:{contact_hash}"
        await redis_client.expire(session_key, ttl_during_cooldown)
        await redis_client.expire(contact_key, ttl_during_cooldown)

        payload = {"email": email, "action_type": action_type.value}
        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 400
        data = response.json()
        expected = VerificationCooldownError(
            remaining_seconds=settings.VERIFICATION_COOLDOWN_SECONDS - 10
        ).detail
        assert data["status"] == 400
        assert data["detail"] == expected
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_business_error_max_requests_exceeded(
        self, http_client: AsyncClient, redis_client, faker: Faker
    ) -> None:
        email = faker.email().lower()
        contact_hash = hash_contact(email)
        rate_limit_key = f"rate_limit:otp:{contact_hash}"
        await redis_client.set(rate_limit_key, settings.VERIFICATION_MAX_REQUEST_COUNT)
        await redis_client.expire(rate_limit_key, settings.OTP_RATE_LIMIT_TTL_SECONDS)

        payload = {"email": email, "action_type": VerificationActionType.USER_CREATION.value}
        response = await http_client.post("/api/v1/verifications", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400
        assert data["detail"] == VerificationMaxRequestsExceededError().detail
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["instance"], str)

    async def test_success_email_case_insensitivity(
        self,
        http_client: AsyncClient,
        redis_client,
        faker: Faker,
        override_otp_sender,
    ) -> None:
        email_original = "Test@Example.COM"
        email_lower = email_original.lower()
        action_type = VerificationActionType.USER_CREATION

        payload_first = {"email": email_original, "action_type": action_type.value}
        response_first = await http_client.post("/api/v1/verifications", json=payload_first)
        assert response_first.status_code == 200
        first_data = VerificationCreateResponse(**response_first.json())
        first_id = first_data.verification_id

        contact_hash = hash_contact(email_lower)
        session_key = f"verification:{first_id}"
        contact_key = f"verification:contact:{contact_hash}"

        ttl_after_cooldown = (
            settings.VERIFICATION_TTL_SECONDS - settings.VERIFICATION_COOLDOWN_SECONDS - 1
        )
        await redis_client.expire(session_key, ttl_after_cooldown)
        await redis_client.expire(contact_key, ttl_after_cooldown)

        payload_second = {"email": email_lower, "action_type": action_type.value}
        response_second = await http_client.post("/api/v1/verifications", json=payload_second)
        assert response_second.status_code == 200
        second_data = VerificationCreateResponse(**response_second.json())
        second_id = second_data.verification_id

        assert str(first_id) == str(second_id)

        rate_limit_key = f"rate_limit:otp:{contact_hash}"
        rate_limit_count = await redis_client.get(rate_limit_key)
        assert rate_limit_count == "2"

    async def test_success_verification_id_uuid_format(
        self,
        http_client: AsyncClient,
        redis_client,
        faker: Faker,
        override_otp_sender,
    ) -> None:
        email = faker.email().lower()
        action_type = VerificationActionType.USER_CREATION
        payload = {"email": email, "action_type": action_type.value}

        response = await http_client.post("/api/v1/verifications", json=payload)
        assert response.status_code == 200
        data = VerificationCreateResponse(**response.json())

        assert len(str(data.verification_id)) == 36
        assert isinstance(data.expires_in, int)
        assert data.expires_in == settings.VERIFICATION_TTL_SECONDS
