import re
import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field
from pydantic.networks import EmailStr


def _normalize_email(value: str) -> str:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.strip().lower())
    return value


NormalizedEmail = Annotated[EmailStr, BeforeValidator(_normalize_email)]


def _validate_password_strength(value: str) -> str:
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", value):
        raise ValueError("Password must contain at least one special character")
    return value


SecurePassword = Annotated[
    str,
    BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
    AfterValidator(_validate_password_strength),
    Field(min_length=8, max_length=128),
]

OtpCode = Annotated[
    str,
    Field(
        pattern=r"^\d{6}$",
        min_length=6,
        max_length=6,
        description="6-digit numeric OTP code",
    ),
]


def _validate_alias_local_part(value: str) -> str:
    if not value:
        raise ValueError("Local part cannot be empty.")

    if len(value) > 57:
        raise ValueError(
            "Local part must be at most 57 characters long to accommodate the random \
        suffix."
        )

    if value.startswith(".") or value.endswith("."):
        raise ValueError("Local part cannot start or end with a dot.")

    if ".." in value:
        raise ValueError("Local part cannot contain consecutive dots.")

    if not re.match(r"^[a-zA-Z0-9!#$%&'*+\-/=?^_`{|}~.]+$", value):
        raise ValueError("Local part contains invalid characters.")

    return value


AliasLocalPart = Annotated[
    str,
    AfterValidator(_validate_alias_local_part),
    Field(
        description="Local part of the alias (prefix provided by user). Max 57 chars, RFC 5322 \
    compliant."
    ),
]
