from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.infrastructure.beget_mail_provider import BegetMailProviderAdapter
from app.infrastructure.stub_otp_sender import StubOTPSender
from app.repositories.aliases import AliasRepository
from app.repositories.domains import DomainRepository
from app.repositories.users import UserRepository
from app.repositories.verification import VerificationRepository
from app.services.aliases import AliasService
from app.services.verifications import VerificationService


@asynccontextmanager
async def alias_service_context() -> AsyncGenerator[AliasService, None]:
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=settings.DEBUG)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            alias_repo = AliasRepository(session)
            domain_repo = DomainRepository(session)
            user_repo = UserRepository(session)
            provider = BegetMailProviderAdapter()
            try:
                service = AliasService(alias_repo, domain_repo, user_repo, provider)
                try:
                    yield service
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            finally:
                await provider.close()
    finally:
        await engine.dispose()


@asynccontextmanager
async def verification_service_context() -> AsyncGenerator[VerificationService, None]:
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        verification_repo = VerificationRepository(redis=redis_client)
        otp_sender = StubOTPSender()
        service = VerificationService(verification_repo, otp_sender)
        yield service
    finally:
        await redis_client.close()
