import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from argon2 import PasswordHasher
from pydantic import TypeAdapter
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user_id, get_token_repository
from app.core.security import hash_token
from app.main import app
from app.models.domain import User, UserRole
from app.repositories.tokens import TokenRepository
from app.schemas.common import SecurePassword
from app.schemas.verification import VerificationActionType, VerificationTokenData

_secure_password_validator = TypeAdapter(SecurePassword)

VALID_TEST_PASSWORD = "ValidP@ssword123!"
NEW_VALID_TEST_PASSWORD = "NewV@lidPass456!"
WRONG_TEST_PASSWORD = "WrongP@ssword123!"
INVALID_TEST_PASSWORD = "InvalidPassword"

TEST_EMAIL = "test@example.com"
TEST_EMAIL_ALT = "new@example.com"
TEST_EMAIL_CONFLICT = "conflict@example.com"

DUMMY_VERIFICATION_TOKEN = "a" * 43
SECOND_DUMMY_VERIFICATION_TOKEN = "b" * 43
INVALID_VERIFICATION_TOKEN = "invalid_token_not_in_redis_1234567890123456"

DUMMY_OTP_CODE = "123456"
INVALID_OTP_CODE = "000000"

_secure_password_validator.validate_python(VALID_TEST_PASSWORD)
_secure_password_validator.validate_python(NEW_VALID_TEST_PASSWORD)
_secure_password_validator.validate_python(WRONG_TEST_PASSWORD)


@pytest.fixture
def password_hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def valid_test_password() -> str:
    return VALID_TEST_PASSWORD


@pytest.fixture
def new_valid_test_password() -> str:
    return NEW_VALID_TEST_PASSWORD


@pytest.fixture
def wrong_test_password() -> str:
    return WRONG_TEST_PASSWORD


@pytest.fixture
def invalid_test_password() -> str:
    return INVALID_TEST_PASSWORD


@pytest.fixture
def test_email() -> str:
    return TEST_EMAIL


@pytest.fixture
def test_email_alt() -> str:
    return TEST_EMAIL_ALT


@pytest.fixture
def test_email_conflict() -> str:
    return TEST_EMAIL_CONFLICT


@pytest.fixture
def generate_test_email() -> Callable[[str], str]:
    def _generate(prefix: str = "test") -> str:
        return f"{prefix}_{uuid.uuid4().hex}@example.com".lower()

    return _generate


@pytest.fixture
def dummy_verification_token() -> str:
    return DUMMY_VERIFICATION_TOKEN


@pytest.fixture
def second_dummy_verification_token() -> str:
    return SECOND_DUMMY_VERIFICATION_TOKEN


@pytest.fixture
def invalid_verification_token() -> str:
    return INVALID_VERIFICATION_TOKEN


@pytest.fixture
def dummy_otp_code() -> str:
    return DUMMY_OTP_CODE


@pytest.fixture
def invalid_otp_code() -> str:
    return INVALID_OTP_CODE


@pytest.fixture
def token_repository(
    override_dependencies: None,
) -> TokenRepository:
    return app.dependency_overrides[get_token_repository]()


@pytest.fixture
async def create_test_user(
    db_session: AsyncSession,
    password_hasher: PasswordHasher,
    generate_test_email: Callable[[str], str],
) -> Callable[..., Awaitable[User]]:
    async def _create(
        password: str,
        email: str | None = None,
        role: UserRole = UserRole.USER,
        is_banned: bool = False,
        is_deleted: bool = False,
    ) -> User:
        user_email = email or generate_test_email(prefix=role)
        password_hash = password_hasher.hash(password)

        stmt = (
            insert(User)
            .values(
                email=user_email,
                password_hash=password_hash,
                role=role,
                is_banned=is_banned,
                deleted_at=datetime.now(UTC) if is_deleted else None,
            )
            .returning(User)
        )

        result = await db_session.execute(stmt)
        return result.scalar_one()

    return _create


@pytest.fixture
async def create_auth_token(
    db_session: AsyncSession,
    token_repository: TokenRepository,
) -> Callable[..., Awaitable[str]]:
    async def _create(user_id: uuid.UUID, role: UserRole = UserRole.USER) -> str:
        token = uuid.uuid4().hex
        hashed = hash_token(token)

        await token_repository.create(
            hashed_token=hashed,
            user_id=user_id,
        )
        return token

    return _create


@pytest.fixture
async def create_verification_token(
    redis_client: Redis,
) -> Callable[..., Awaitable[str]]:
    async def _create(
        email: str,
        action_type: VerificationActionType,
        raw_token: str | None = None,
    ) -> str:
        token = raw_token or uuid.uuid4().hex
        token_hash = hash_token(token)
        token_key = f"vtoken:{token_hash}"
        token_data = VerificationTokenData(
            contact=email,
            action_type=action_type,
        )
        await redis_client.set(
            token_key,
            token_data.model_dump_json(),
            ex=settings.VERIFICATION_TOKEN_TTL_SECONDS,
        )
        return token

    return _create


@pytest.fixture
async def authenticated_headers(
    create_test_user: Callable[..., Awaitable[User]],
    create_auth_token: Callable[..., Awaitable[str]],
) -> Callable[..., Awaitable[dict[str, str]]]:
    async def _get_headers(role: UserRole = UserRole.USER) -> dict[str, str]:
        user = await create_test_user(role=role, password=VALID_TEST_PASSWORD)
        token = await create_auth_token(user_id=user.id, role=role)
        return {"Authorization": f"Bearer {token}"}

    return _get_headers


@pytest.fixture
def override_current_user_id(
    override_dependencies: None,
) -> Callable[[uuid.UUID], None]:
    def _override(user_id: uuid.UUID) -> None:
        async def mock_get_current_user_id() -> uuid.UUID:
            return user_id

        app.dependency_overrides[get_current_user_id] = mock_get_current_user_id

    yield _override

    if get_current_user_id in app.dependency_overrides:
        del app.dependency_overrides[get_current_user_id]
