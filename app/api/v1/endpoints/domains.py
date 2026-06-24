import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_current_user_id, get_domain_service
from app.core.rate_limiter import limiter
from app.schemas.responses import DomainResponse
from app.services.domains import DomainService

router = APIRouter()


@router.get(
    "",
    response_model=list[DomainResponse],
    status_code=status.HTTP_200_OK,
    summary="Get available domains",
    description="Retrieve a list of all available domains for alias creation.",
    responses={
        200: {"description": "List of domains successfully retrieved"},
        401: {"description": "Invalid or expired token"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_DOMAINS)
async def get_domains(
    request: Request,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    service: Annotated[DomainService, Depends(get_domain_service)],
) -> list[DomainResponse]:
    return await service.get_domains()
