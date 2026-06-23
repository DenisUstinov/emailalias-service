from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import UserRole


class TokenCreateResponse(BaseModel):
    access_token: str = Field(..., description="Opaque session token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token lifetime in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "randomly_generated_string_here",
                "token_type": "bearer",
                "expires_in": 900,
            }
        }
    )


class UserAdminUpdateResponse(BaseModel):
    is_banned: bool = Field(..., description="Current ban status of the user")
    role: UserRole = Field(..., description="Current role assignment of the user")
    updated_at: datetime = Field(..., description="Last modification timestamp in UTC")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "is_banned": True,
                "role": "provider",
                "updated_at": "2026-05-20T15:30:00Z",
            }
        },
    )


class UserCreateResponse(BaseModel):
    email: str = Field(..., description="Normalized email address of the user")
    created_at: datetime = Field(..., description="Account creation timestamp in UTC")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "created_at": "2026-01-15T10:30:00Z",
            }
        },
    )


class UserDeleteResponse(BaseModel):
    deleted_at: datetime = Field(..., description="Account deletion timestamp in UTC")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "deleted_at": "2026-05-20T15:30:00Z",
            }
        },
    )


class UserUpdateResponse(BaseModel):
    email: str = Field(..., description="Normalized email address of the user")
    updated_at: datetime = Field(..., description="Last modification timestamp in UTC")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "updated_at": "2026-05-20T15:30:00Z",
            }
        },
    )


class VerificationConfirmResponse(BaseModel):
    verification_token: str = Field(
        ...,
        min_length=43,
        max_length=43,
        description="Opaque cryptographically secure token proving successful email verification; \
        present this token in subsequent critical operations",
    )
    expires_in: int = Field(
        ...,
        gt=0,
        description="Time-to-live of the verification token in seconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verification_token": "F7xK9mP2nQ4vL8wR3tY6uZ1sA5bC0dE2gH7jN9pM4xW",
                "expires_in": 900,
            }
        }
    )


class VerificationCreateResponse(BaseModel):
    verification_id: UUID = Field(
        ...,
        description="Unique identifier of the verification session; use this ID to submit the OTP \
        code for confirmation",
    )
    expires_in: int = Field(
        ...,
        gt=0,
        description="Time-to-live of the verification session in seconds",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verification_id": "550e8400-e29b-41d4-a716-446655440000",
                "expires_in": 900,
            }
        }
    )
