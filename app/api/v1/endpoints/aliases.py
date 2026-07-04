import uuid
from typing import Annotated

from celery import chain
from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_alias_service, get_current_user_id
from app.core.rate_limiter import limiter
from app.infrastructure.celery.tasks import (
    configure_forwarding_task,
    create_mailbox_task,
)
from app.schemas.requests import AliasCreateRequest
from app.schemas.responses import AliasCreateResponse
from app.services.aliases import AliasService

router = APIRouter()


@router.post(
    "",
    response_model=AliasCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new alias",
    description="Create a new email alias attached to a specified domain. A random 6-character \
    suffix will be appended to the user-provided local part. The physical mailbox \
    creation and forwarding configuration are processed asynchronously in the background.",
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
    workflow = chain(
        create_mailbox_task.s(str(response.id)),
        configure_forwarding_task.s(),
    )
    workflow.apply_async()
    return response
