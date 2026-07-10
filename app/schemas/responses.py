from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import UserRole


class AliasCreateResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier of the alias")
    email: str = Field(..., description="Fully generated email address; activation is in progress")
    status: str = Field(
        ..., description="Current provisioning status of the alias (pending, active, failed)"
    )
    created_at: datetime = Field(..., description="Alias creation timestamp in UTC")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "bugtracker.a3F9x2@example.com",
                "status": "pending",
                "created_at": "2026-06-26T10:30:00Z",
            }
        },
    )


class AliasListItemResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier of the alias")
    email: str = Field(..., description="Fully generated email address")
    status: str = Field(..., description="Current status of the alias (pending, active, failed)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "bugtracker.a3F9x2@example.com",
                "status": "active",
            }
        },
    )


class DomainResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier of the domain in the local database")
    fqdn: str = Field(..., description="Fully qualified domain name used for mailbox creation")
    is_default: bool = Field(
        ...,
        description="Flag indicating if this is the default domain for free users",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "fqdn": "example.com",
                "is_default": True,
            }
        },
    )


class TokenCreateResponse(BaseModel):
    access_token: str = Field(..., description="Opaque session token")
    token_type: str = Field(default="bearer", description="Token type")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "randomly_generated_string_here",
                "token_type": "bearer",
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
                "role": "user",
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
