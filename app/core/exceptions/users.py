from fastapi import status

from .base import AppException


class CurrentPasswordInvalidError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )


class CurrentPasswordRequiredError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is required",
        )


class EmailAlreadyExistsError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use.",
        )


class UserBannedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is banned.",
        )


class UserNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
