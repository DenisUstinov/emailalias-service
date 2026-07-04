from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.infrastructure.mail_provider import BegetMailProviderAdapter
from app.repositories.aliases import AliasRepository
from app.repositories.domains import DomainRepository
from app.repositories.users import UserRepository
from app.services.aliases import AliasService


@asynccontextmanager
async def worker_context() -> AsyncGenerator[AliasService, None]:
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=settings.DEBUG)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            alias_repo = AliasRepository(session)
            domain_repo = DomainRepository(session)
            user_repo = UserRepository(session)
            provider = BegetMailProviderAdapter()
            service = AliasService(alias_repo, domain_repo, user_repo, provider)
            try:
                yield service
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()
