import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, AuthenticationRequiredError
from app.core.notifications import OTPSender
from app.core.security import hash_token
from app.infrastructure.beget_mail_provider import BegetMailProviderAdapter
from app.infrastructure.stub_otp_sender import StubOTPSender
from app.models.database import AsyncSessionLocal
from app.models.domain import UserRole
from app.repositories.aliases import AliasRepository
from app.repositories.domains import DomainRepository
from app.repositories.tokens import TokenRepository
from app.repositories.users import UserRepository
from app.repositories.verification import VerificationRepository
from app.services.aliases import AliasService
from app.services.domains import DomainService
from app.services.passwords import PasswordService
from app.services.tokens import TokenService
from app.services.users import UserService
from app.services.verifications import VerificationService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis(request: Request) -> AsyncGenerator[Redis, None]:
    yield request.app.state.redis


async def get_token_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[TokenRepository, None]:
    repository = TokenRepository(session=db)
    try:
        yield repository
    finally:
        pass


def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> UserService:
    user_repo = UserRepository(session=db)
    verification_repo = VerificationRepository(redis=redis_client)
    verification_service = VerificationService(verification_repo, get_otp_sender())
    token_repo = TokenRepository(session=db)
    return UserService(
        user_repo=user_repo,
        verification_service=verification_service,
        token_repo=token_repo,
    )


def get_password_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> PasswordService:
    user_repo = UserRepository(session=db)
    verification_repo = VerificationRepository(redis=redis_client)
    verification_service = VerificationService(verification_repo, get_otp_sender())
    token_repo = TokenRepository(session=db)
    return PasswordService(
        user_repo=user_repo,
        verification_service=verification_service,
        token_repo=token_repo,
    )


def get_token_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenService:
    user_repo = UserRepository(session=db)
    token_repo = TokenRepository(session=db)
    return TokenService(user_repo=user_repo, token_repo=token_repo)


def get_otp_sender() -> OTPSender:
    return StubOTPSender()


def get_verification_service(
    redis_client: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
    otp_sender: Annotated[OTPSender, Depends(get_otp_sender)],
) -> VerificationService:
    verification_repo = VerificationRepository(redis=redis_client)
    return VerificationService(
        verification_repo=verification_repo,
        otp_sender=otp_sender,
    )


def get_domain_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DomainService:
    domain_repo = DomainRepository(session=db)
    return DomainService(domain_repo=domain_repo)


def get_alias_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AliasService:
    alias_repo = AliasRepository(session=db)
    domain_repo = DomainRepository(session=db)
    user_repo = UserRepository(session=db)
    provider = BegetMailProviderAdapter()
    return AliasService(
        alias_repo=alias_repo,
        domain_repo=domain_repo,
        user_repo=user_repo,
        mail_provider=provider,
    )


security = HTTPBearer()


async def _get_current_user_with_role(
    token_repo: TokenRepository,
    credentials: HTTPAuthorizationCredentials,
    required_role: UserRole,
) -> uuid.UUID:
    raw_token = credentials.credentials
    hashed_token = hash_token(raw_token)

    token = await token_repo.get(hashed_token)

    if not token:
        raise AuthenticationRequiredError()

    if token.user.role != required_role:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{required_role.value.capitalize()} access required",
        )

    return token.user.id


async def get_current_user_id(
    token_repo: Annotated[TokenRepository, Depends(get_token_repository)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> uuid.UUID:
    return await _get_current_user_with_role(token_repo, credentials, UserRole.USER)


async def get_current_admin_user_id(
    token_repo: Annotated[TokenRepository, Depends(get_token_repository)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> uuid.UUID:
    return await _get_current_user_with_role(token_repo, credentials, UserRole.ADMIN)
