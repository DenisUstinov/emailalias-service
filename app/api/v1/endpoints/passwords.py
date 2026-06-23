from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_password_service
from app.core.rate_limiter import limiter
from app.schemas.requests import PasswordUpdateRequest
from app.services.passwords import PasswordService

router = APIRouter()


@router.patch(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update user password",
    description="Update user password using a pre-verified email session via OTP.",
    responses={
        204: {"description": "Password successfully updated"},
        400: {"description": "Email not verified"},
        403: {"description": "Account is banned"},
        404: {"description": "User not found"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_PASSWORD_UPDATE)
async def update_password(
    request: Request,
    data: PasswordUpdateRequest,
    service: Annotated[PasswordService, Depends(get_password_service)],
) -> None:
    await service.update_password(request=data)
