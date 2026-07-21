from .aliases import (
    AliasActiveLimitExceededError,
    AliasCollisionError,
    AliasDomainNotFoundError,
    AliasMonthlyLimitExceededError,
    AliasPremiumDomainRequiresSubscriptionError,
)
from .base import AppException
from .common import (
    ExternalProviderRejectionError,
    ExternalProviderUnavailableError,
)
from .tokens import (
    InvalidCredentialsError,
    TokenMissingError,
    TokenPasswordAttemptsBlockedError,
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
    "ContactNotVerifiedError",
    "CurrentPasswordInvalidError",
    "CurrentPasswordRequiredError",
    "EmailAlreadyExistsError",
    "ExternalProviderRejectionError",
    "ExternalProviderUnavailableError",
    "InvalidCredentialsError",
    "TokenMissingError",
    "TokenPasswordAttemptsBlockedError",
    "UserBannedError",
    "UserNotFoundError",
    "VerificationAttemptsLimitExceededError",
    "VerificationCooldownError",
    "VerificationInvalidOTPError",
    "VerificationMaxAttemptsExceededError",
    "VerificationMaxRequestsExceededError",
    "VerificationSessionNotFoundError",
]
