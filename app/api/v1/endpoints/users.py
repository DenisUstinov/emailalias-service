import uuid
from typing import Annotated

from celery import group
from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import (
    get_alias_service,
    get_current_admin_user_id,
    get_current_user_id,
    get_user_service,
)
from app.core.rate_limiter import limiter
from app.infrastructure.celery.tasks import update_alias_forwarding_task
from app.schemas.requests import (
    UserAdminUpdateRequest,
    UserCreateRequest,
    UserDeleteRequest,
    UserUpdateRequest,
)
from app.schemas.responses import UserAdminUpdateResponse, UserCreateResponse, UserUpdateResponse
from app.services.aliases import AliasService
from app.services.users import UserService

router = APIRouter()


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete current user account",
    description="Permanently delete the authenticated user's account after \
    email verification via OTP.",
    responses={
        204: {"description": "User account successfully deleted"},
        400: {"description": "Email not verified or invalid verification token"},
        401: {"description": "Invalid or expired token"},
        403: {"description": "Account is banned"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_USER_DELETION)
async def delete_user_me(
    request: Request,
    data: UserDeleteRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    await service.delete_user(user_id=user_id, verification_token=data.verification_token)


@router.patch(
    "/me",
    response_model=UserUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Partially update the authenticated user's email or password.",
    responses={
        200: {"description": "User profile successfully updated"},
        400: {"description": "Invalid current password or unverified email session"},
        401: {"description": "Invalid or expired token"},
        404: {"description": "User not found"},
        409: {"description": "Email already in use"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_USER_UPDATE)
async def update_user_me(
    request: Request,
    data: UserUpdateRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
    alias_service: Annotated[AliasService, Depends(get_alias_service)],
) -> UserUpdateResponse:
    response = await service.update_user(
        user_id=user_id,
        email=data.email,
        new_password=data.new_password,
        current_password=data.current_password,
        verification_token=data.verification_token,
    )

    if data.email is not None:
        alias_ids = await alias_service.get_active_alias_ids(user_id)
        if alias_ids:
            workflow = group(
                update_alias_forwarding_task.s(str(alias_id)) for alias_id in alias_ids
            )
            workflow.apply_async()

    return response


@router.patch(
    "/{user_id}",
    response_model=UserAdminUpdateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user by admin",
    description="Partially update user's ban status or role. Accessible only to admin users.",
    responses={
        200: {"description": "User successfully updated by admin"},
        401: {"description": "Invalid or expired token"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_USER_UPDATE)
async def update_user_admin(
    request: Request,
    user_id: uuid.UUID,
    data: UserAdminUpdateRequest,
    admin_id: Annotated[uuid.UUID, Depends(get_current_admin_user_id)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserAdminUpdateResponse:
    return await service.update_user_admin(
        user_id=user_id,
        is_banned=data.is_banned,
        role=data.role,
    )


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user account with email and password.",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Email not verified or invalid verification token"},
        409: {"description": "User with this email already exists"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_USER_CREATION)
async def create_user(
    request: Request,
    data: UserCreateRequest,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserCreateResponse:
    return await service.create_user(data)
