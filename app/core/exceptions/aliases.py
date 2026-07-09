from fastapi import status

from .base import AppException


class AliasCollisionError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alias with this configuration already exists",
        )


class AliasDomainNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found",
        )


class AliasMonthlyLimitExceededError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Monthly alias creation limit exceeded for free tier",
        )


class AliasActiveLimitExceededError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active alias limit exceeded for free tier",
        )


class AliasPremiumDomainRequiresSubscriptionError(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Domain requires active subscription",
        )
