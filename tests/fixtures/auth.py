import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from pydantic import TypeAdapter
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_token_repository
from app.core.security import hash_token
from app.main import app
from app.models.domain import User, UserRole
from app.repositories.tokens import TokenRepository
from app.schemas.common import SecurePassword
from app.schemas.token import TokenData

_secure_password_validator = TypeAdapter(SecurePassword)

VALID_TEST_PASSWORD = "ValidP@ssword123!"
NEW_VALID_TEST_PASSWORD = "NewV@lidPass456!"
INVALID_TEST_PASSWORD = "InvalidPassword"

TEST_EMAIL = "test@example.com"
TEST_EMAIL_ALT = "new@example.com"
TEST_EMAIL_CONFLICT = "conflict@example.com"

_secure_password_validator.validate_python(VALID_TEST_PASSWORD)
_secure_password_validator.validate_python(NEW_VALID_TEST_PASSWORD)


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
    async def _create(user_id: uuid.UUID, role: UserRole, ttl_seconds: int = 3600) -> str:
        token = uuid.uuid4().hex
        hashed = hash_token(token)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

        await token_repository.create(
            hashed_token=hashed,
            data=TokenData(user_id=user_id, role=role, expires_at=expires_at),
            expire_seconds=ttl_seconds,
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
