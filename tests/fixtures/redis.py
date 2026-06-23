from collections.abc import AsyncGenerator

import pytest
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings


@pytest.fixture(scope="session")
async def redis_pool() -> AsyncGenerator[ConnectionPool, None]:
    pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=5,
        decode_responses=True,
        socket_keepalive=True,
    )
    yield pool
    await pool.disconnect()


@pytest.fixture(scope="function")
async def redis_client(redis_pool: ConnectionPool) -> AsyncGenerator[Redis, None]:
    client = Redis(connection_pool=redis_pool)
    yield client
    await client.flushdb()
    await client.aclose()
