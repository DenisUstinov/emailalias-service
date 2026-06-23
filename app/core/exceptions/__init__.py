from .base import AppException
from .common import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
)
from .users import (
    CurrentPasswordInvalidError,
    CurrentPasswordRequiredError,
    EmailAlreadyExistsError,
    UserBannedError,
    UserNotFoundError,
)
from .verifications import (
    EmailNotVerifiedError,
    VerificationAttemptsLimitExceededError,
    VerificationCooldownError,
    VerificationInvalidOTPError,
    VerificationMaxAttemptsExceededError,
    VerificationMaxRequestsExceededError,
    VerificationSessionNotFoundError,
)

__all__ = [
    "AppException",
    "AuthenticationRequiredError",
    "CurrentPasswordInvalidError",
    "CurrentPasswordRequiredError",
    "EmailAlreadyExistsError",
    "EmailNotVerifiedError",
    "InvalidCredentialsError",
    "UserBannedError",
    "UserNotFoundError",
    "VerificationAttemptsLimitExceededError",
    "VerificationCooldownError",
    "VerificationInvalidOTPError",
    "VerificationMaxAttemptsExceededError",
    "VerificationMaxRequestsExceededError",
    "VerificationSessionNotFoundError",
]
