from .aliases import (
    AliasActiveLimitExceededError,
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from .base import AppException
from .common import (
    AuthenticationRequiredError,
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
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
    "AliasActiveLimitExceededError",
    "AliasCollisionError",
    "AliasDomainNotFoundError",
    "AliasMonthlyLimitExceededError",
    "AliasPremiumDomainRequiresSubscriptionError",
    "AppException",
    "AuthenticationRequiredError",
    "CurrentPasswordInvalidError",
    "CurrentPasswordRequiredError",
    "EmailAlreadyExistsError",
    "ExternalProviderRejectionError",
    "ExternalProviderUnavailableError",
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
