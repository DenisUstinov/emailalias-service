from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.domain import UserRole
from app.schemas.common import NormalizedEmail, OtpCode, SecurePassword
from app.schemas.verification import VerificationActionType


class PasswordUpdateRequest(BaseModel):
    email: NormalizedEmail = Field(
        ...,
        max_length=254,
        description="Email address (RFC 5322), normalized to lowercase with Unicode NFC.",
    )
    new_password: SecurePassword = Field(
        ...,
        description="New password: 8–128 characters, requires one digit and one special character.",
    )
    verification_token: str = Field(
        ...,
        min_length=43,
        max_length=43,
        description="Verification token proving ownership of email for password reset operation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "new_password": "NewStrongP@ss456",
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            }
        }
    )


class TokenCreateRequest(BaseModel):
    email: NormalizedEmail = Field(
        ...,
        max_length=254,
        description="User email address.",
    )
    password: SecurePassword = Field(
        ...,
        description="User password.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "StrongP@ss123",
            }
        }
    )


class UserAdminUpdateRequest(BaseModel):
    is_banned: bool | None = Field(
        default=None,
        description="Target user ban status.",
    )
    role: UserRole | None = Field(
        default=None,
        description="Target user role assignment.",
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        update_fields = {"is_banned", "role"}
        if not self.model_fields_set.intersection(update_fields):
            raise ValueError(
                "At least one field must be provided: " + ", ".join(sorted(update_fields)) + "."
            )
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_banned": True,
                "role": "user",
            }
        }
    )


class UserCreateRequest(BaseModel):
    email: NormalizedEmail = Field(
        ...,
        max_length=254,
        description="Email address (RFC 5322), normalized to lowercase with Unicode NFC.",
    )
    password: SecurePassword = Field(
        ...,
        description="Password: 8–128 characters, requires one digit and one special character.",
    )
    verification_token: str = Field(
        ...,
        min_length=43,
        max_length=43,
        description="Verification token proving email ownership for user creation operation.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "StrongP@ss123",
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            }
        }
    )


class UserDeleteRequest(BaseModel):
    verification_token: str = Field(
        ...,
        min_length=43,
        max_length=43,
        description="Verification token proving email ownership for account deletion operation.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            }
        }
    )


class UserUpdateRequest(BaseModel):
    email: NormalizedEmail | None = Field(
        default=None,
        max_length=254,
        description="New email address (RFC 5322), normalized to lowercase with Unicode NFC.",
    )
    new_password: SecurePassword | None = Field(
        default=None,
        description="New password: 8–128 characters, requires one digit and one special character.",
    )
    current_password: SecurePassword | None = Field(
        default=None,
        description="Current password for confirmation when changing password.",
    )
    verification_token: str | None = Field(
        default=None,
        min_length=43,
        max_length=43,
        description="Verification token proving ownership of new email address. Required only when \
        updating email.",
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        update_fields = {"email", "new_password"}
        if not self.model_fields_set.intersection(update_fields):
            raise ValueError(
                "At least one field must be provided: " + ", ".join(sorted(update_fields)) + "."
            )
        return self

    @model_validator(mode="after")
    def validate_email_change_requires_token(self) -> Self:
        if "email" in self.model_fields_set and self.verification_token is None:
            raise ValueError("Verification token is required when updating email address.")
        return self

    @model_validator(mode="after")
    def validate_password_change_requires_current(self) -> Self:
        if "new_password" in self.model_fields_set and self.current_password is None:
            raise ValueError("Current password is required when setting a new password.")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "new_password": "StrongP@ss456",
                "current_password": "StrongP@ss123",
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
            }
        }
    )


class VerificationConfirmRequest(BaseModel):
    otp_code: OtpCode = Field(
        ...,
        description="Six-digit one-time password received via email for verification confirmation",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "otp_code": "123456",
            }
        }
    )


class VerificationCreateRequest(BaseModel):
    email: NormalizedEmail = Field(
        ...,
        max_length=254,
        description="Email address to verify ownership of",
    )
    action_type: VerificationActionType = Field(
        ...,
        description="Business purpose for which the verification is requested",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "action_type": "user_creation",
            }
        }
    )
