import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import quote_plus

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from faker import Faker
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.dependencies import get_db, get_redis, get_token_repository
from app.main import app
from app.repositories.tokens import TokenRepository

pytest_plugins = [
    "tests.fixtures.redis",
    "tests.fixtures.auth",
    "tests.fixtures.factories",
    "tests.fixtures.email",
    "tests.fixtures.mocks",
    "tests.fixtures.deterministic",
]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def faker_seed() -> int:
    return 42


@pytest.fixture(scope="session", autouse=True)
def set_faker_seed(_session_faker: Faker, faker_seed: int) -> None:
    _session_faker.seed_instance(faker_seed)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    db_name = f"{settings.POSTGRES_DB}_test"
    pwd = settings.POSTGRES_PASSWORD.get_secret_value()
    return (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{quote_plus(pwd)}@"
        f"{settings.POSTGRES_HOST}:5432/{db_name}"
    )


@pytest.fixture(scope="session", autouse=True)
async def manage_test_database(
    test_database_url: str,
) -> AsyncGenerator[None, None]:
    admin_url = (
        f"postgresql://{settings.POSTGRES_USER}:"
        f"{quote_plus(settings.POSTGRES_PASSWORD.get_secret_value())}@"
        f"{settings.POSTGRES_HOST}:5432/postgres"
    )
    db_name = f"{settings.POSTGRES_DB}_test"

    conn = await asyncpg.connect(admin_url)
    db_exists = await conn.fetchval(
        "SELECT 1 FROM pg_catalog.pg_database WHERE datname = $1", db_name
    )
    if not db_exists:
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    await conn.close()

    alembic_cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    escaped_url = test_database_url.replace("%", "%%")
    alembic_cfg.set_main_option("sqlalchemy.url", escaped_url)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    yield

    conn = await asyncpg.connect(admin_url)
    await conn.execute(
        "SELECT pg_terminate_backend(pid) "
        "FROM pg_stat_activity "
        "WHERE datname = $1 AND pid <> pg_backend_pid()",
        db_name,
    )
    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    await conn.close()


@pytest.fixture(scope="session")
async def test_engine(
    test_database_url: str, manage_test_database: None
) -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        test_database_url,
        echo=False,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture(scope="function")
async def db_session(
    test_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        async with session_factory(bind=conn) as session:
            try:
                yield session
            finally:
                await trans.rollback()


@pytest.fixture(scope="function")
async def override_dependencies(
    db_session: AsyncSession, redis_client: Redis
) -> AsyncGenerator[None, None]:
    original_overrides = app.dependency_overrides.copy()

    async def mock_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def mock_get_redis() -> AsyncGenerator[Redis, None]:
        yield redis_client

    def mock_get_token_repository() -> TokenRepository:
        return TokenRepository(redis=redis_client)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_token_repository] = mock_get_token_repository

    yield

    app.dependency_overrides = original_overrides


@pytest.fixture(scope="function")
async def http_client(
    override_dependencies: None,
) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
