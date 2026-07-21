from fastapi import status

from .base import AppException


class ExternalProviderUnavailableError(AppException):
    def __init__(self, detail: str = "External provider is unavailable") -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class ExternalProviderRejectionError(AppException):
    def __init__(self, detail: str = "External provider rejected the request") -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )
