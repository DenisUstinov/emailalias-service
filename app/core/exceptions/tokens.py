from fastapi import status

from .base import AppException


class InvalidCredentialsError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


class TokenMissingError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is required",
        )


class TokenPasswordAttemptsBlockedError(AppException):
    def __init__(self, remaining_seconds: int) -> None:
        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Password attempts temporarily blocked. Try again in {remaining_seconds} \
            seconds.",
        )
