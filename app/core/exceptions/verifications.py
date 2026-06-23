from fastapi import status

from .base import AppException


class VerificationCooldownError(AppException):
    def __init__(self, remaining_seconds: int) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please wait {remaining_seconds} seconds before requesting again",
        )


class VerificationMaxAttemptsExceededError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many verification attempts. Please request a new code",
        )


class VerificationMaxRequestsExceededError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum OTP requests reached for this email",
        )


class VerificationSessionNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification session not found or expired",
        )


class VerificationAttemptsLimitExceededError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification attempts limit exceeded",
        )


class VerificationInvalidOTPError(AppException):
    def __init__(self, attempts_remaining: int) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP. Attempts remaining: {attempts_remaining}",
        )


class EmailNotVerifiedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified. Please verify your email before registration.",
        )
