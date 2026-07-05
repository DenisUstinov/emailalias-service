from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import get_verification_service
from app.core.rate_limiter import limiter
from app.infrastructure.celery.tasks import send_otp_task
from app.schemas.requests import VerificationConfirmRequest, VerificationCreateRequest
from app.schemas.responses import VerificationConfirmResponse, VerificationCreateResponse
from app.services.verifications import VerificationService

router = APIRouter()


@router.patch(
    "/{verification_id}",
    response_model=VerificationConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm contact verification",
    description="Verify ownership of a contact (email or phone) by submitting the OTP code \
    using the verification session identifier.",
    responses={
        200: {"description": "Contact successfully verified, verification token issued"},
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
    return await service.confirm_verification(
        verification_id=str(verification_id),
        otp_code=data.otp_code,
    )


@router.post(
    "",
    response_model=VerificationCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate contact verification",
    description="Send an OTP code to the specified contact (email or phone) to verify ownership \
    for a specific action. The OTP delivery is processed asynchronously in the background.",
    responses={
        202: {
            "description": "Verification request accepted and OTP delivery queued for background \
            processing"
        },
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
        contact=data.email,
        action_type=data.action_type,
    )
    send_otp_task.apply_async(args=[data.email, str(result.verification_id)])
    return result
