import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notifications import EmailSender, StubEmailSender
from app.core.security import hash_token
from app.models.database import AsyncSessionLocal
from app.models.domain import UserRole
from app.repositories.tokens import TokenRepository
from app.repositories.users import UserRepository
from app.repositories.verification import VerificationRepository
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
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> AsyncGenerator[TokenRepository, None]:
    repository = TokenRepository(redis=redis_client)
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
    verification_service = VerificationService(verification_repo, get_email_sender())
    token_repo = TokenRepository(redis=redis_client)
    user_repo_for_tokens = UserRepository(session=db)
    token_service = TokenService(user_repo=user_repo_for_tokens, token_repo=token_repo)
    return UserService(
        user_repo=user_repo,
        verification_service=verification_service,
        token_service=token_service,
    )


def get_password_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[Redis, Depends(get_redis)],
) -> PasswordService:
    user_repo = UserRepository(session=db)
    verification_repo = VerificationRepository(redis=redis_client)
    verification_service = VerificationService(verification_repo, get_email_sender())
    token_repo = TokenRepository(redis=redis_client)
    user_repo_for_tokens = UserRepository(session=db)
    token_service = TokenService(user_repo=user_repo_for_tokens, token_repo=token_repo)
    return PasswordService(
        user_repo=user_repo,
        verification_service=verification_service,
        token_service=token_service,
    )


def get_token_service(
    redis_client: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenService:
    user_repo = UserRepository(session=db)
    token_repo = TokenRepository(redis=redis_client)
    return TokenService(user_repo=user_repo, token_repo=token_repo)


def get_email_sender() -> EmailSender:
    return StubEmailSender()


def get_verification_service(
    redis_client: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> VerificationService:
    verification_repo = VerificationRepository(redis=redis_client)
    return VerificationService(
        verification_repo=verification_repo,
        email_sender=email_sender,
    )


security = HTTPBearer()


async def _get_current_user_with_role(
    token_repo: TokenRepository,
    credentials: HTTPAuthorizationCredentials,
    required_role: UserRole,
) -> uuid.UUID:
    raw_token = credentials.credentials
    hashed_token = hash_token(raw_token)

    token_data = await token_repo.get(hashed_token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_data.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{required_role.value.capitalize()} access required",
        )

    return token_data.user_id


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
