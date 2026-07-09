import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_alias_service, get_current_user_id
from app.core.rate_limiter import limiter
from app.infrastructure.celery.tasks import deprovision_alias_task, provision_alias_task
from app.schemas.requests import AliasCreateRequest
from app.schemas.responses import AliasCreateResponse, AliasListItemResponse
from app.services.aliases import AliasService

router = APIRouter()


@router.get(
    "",
    response_model=list[AliasListItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user aliases",
    description="Retrieve a list of all non-deleted aliases for the authenticated user.",
    responses={
        200: {"description": "List of aliases successfully retrieved"},
        401: {"description": "Invalid or expired token"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_ALIASES_LIST)
async def get_aliases(
    request: Request,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[AliasService, Depends(get_alias_service)],
) -> list[AliasListItemResponse]:
    return await service.get_aliases(user_id=user_id)


@router.delete(
    "/{alias_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an alias",
    description="Soft-delete an email alias and mark it as removed.",
    responses={
        204: {"description": "Alias successfully deleted"},
        401: {"description": "Invalid or expired token"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_ALIAS_DELETION)
async def delete_alias(
    request: Request,
    alias_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[AliasService, Depends(get_alias_service)],
) -> None:
    await service.delete_alias(alias_id=alias_id, user_id=user_id)
    deprovision_alias_task.apply_async(args=[str(alias_id)])


@router.post(
    "",
    response_model=AliasCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new alias",
    description="Create a new email alias attached to a specified domain.",
    responses={
        202: {
            "description": "Alias creation request accepted and queued for background processing"
        },
        401: {"description": "Invalid or expired token"},
        402: {"description": "Monthly alias creation limit exceeded for free tier"},
        403: {"description": "Domain requires active subscription"},
        404: {"description": "Domain not found"},
        409: {"description": "Alias with this configuration already exists"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_ALIAS_CREATION)
async def create_alias(
    request: Request,
    data: AliasCreateRequest,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[AliasService, Depends(get_alias_service)],
) -> AliasCreateResponse:
    response = await service.create_alias(
        user_id=user_id,
        domain_id=data.domain_id,
        local_part=data.local_part,
    )
    provision_alias_task.apply_async(args=[str(response.id)])
    return response
