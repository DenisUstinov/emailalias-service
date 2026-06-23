from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_verification_service
from app.core.rate_limiter import limiter
from app.schemas.requests import VerificationConfirmRequest, VerificationCreateRequest
from app.schemas.responses import VerificationConfirmResponse, VerificationCreateResponse
from app.services.verifications import VerificationService

router = APIRouter()


@router.patch(
    "/{verification_id}",
    response_model=VerificationConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm email verification",
    description="Verify ownership of email address by submitting the OTP code received via email \
    using the verification session identifier.",
    responses={
        200: {"description": "Email successfully verified, verification token issued"},
        400: {"description": "Invalid OTP or verification attempts limit exceeded"},
        404: {"description": "Verification session not found or expired"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_VERIFICATION_CONFIRMATION)
async def confirm_verification(
    request: Request,
    verification_id: UUID,
    data: VerificationConfirmRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> VerificationConfirmResponse:
    result = await service.confirm_verification(
        verification_id=str(verification_id),
        otp_code=data.otp_code,
    )
    return VerificationConfirmResponse(
        verification_token=result["verification_token"],
        expires_in=result["expires_in"],
    )


@router.post(
    "",
    response_model=VerificationCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate email verification",
    description="Send an OTP code to the specified email address to verify ownership for a \
    specific action.",
    responses={
        200: {"description": "OTP successfully sent"},
        400: {"description": "Cooldown not elapsed or limits exceeded"},
        422: {"description": "Validation error in request data"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_VERIFICATION_CREATION)
async def create_verification(
    request: Request,
    data: VerificationCreateRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> VerificationCreateResponse:
    result = await service.create_verification(
        email=data.email,
        action_type=data.action_type,
    )
    return VerificationCreateResponse(
        verification_id=result["verification_id"],
        expires_in=result["expires_in"],
    )
