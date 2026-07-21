from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_token_service
from app.core.rate_limiter import limiter
from app.schemas.requests import TokenCreateRequest
from app.schemas.responses import TokenCreateResponse
from app.services.tokens import TokenService

router = APIRouter()


@router.post(
    "",
    response_model=TokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create authentication token",
    description="Authenticate user with email and password to obtain an access token.",
    responses={
        201: {"description": "Authentication token successfully created"},
        401: {"description": "Invalid email or password"},
        403: {"description": "Account is banned"},
        422: {"description": "Validation error in request data"},
        423: {"description": "Password attempts temporarily blocked"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Service temporarily unavailable"},
    },
)
@limiter.limit(settings.RATE_LIMIT_TOKEN_CREATION)
async def create_token(
    request: Request,
    data: TokenCreateRequest,
    service: Annotated[TokenService, Depends(get_token_service)],
) -> TokenCreateResponse:
    return await service.create_token(
        email=data.email,
        password=data.password,
    )
