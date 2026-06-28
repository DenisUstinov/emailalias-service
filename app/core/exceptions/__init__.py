from .aliases import (
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
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
    ContactNotVerifiedError,
    VerificationAttemptsLimitExceededError,
    VerificationCooldownError,
    VerificationInvalidOTPError,
    VerificationMaxAttemptsExceededError,
    VerificationMaxRequestsExceededError,
    VerificationSessionNotFoundError,
)

__all__ = [
    "AliasCollisionError",
    "AliasDomainNotFoundError",
    "AliasMonthlyLimitExceededError",
    "AliasPremiumDomainRequiresSubscriptionError",
    "AppException",
    "AuthenticationRequiredError",
    "CurrentPasswordInvalidError",
    "CurrentPasswordRequiredError",
    "EmailAlreadyExistsError",
    "ContactNotVerifiedError",
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
