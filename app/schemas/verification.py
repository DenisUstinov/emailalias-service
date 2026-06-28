from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VerificationActionType(StrEnum):
    USER_CREATION = "user_creation"
    PASSWORD_RESET = "password_reset"
    EMAIL_CHANGE = "email_change"
    USER_DELETION = "user_deletion"


class VerificationSessionData(BaseModel):
    contact: str = Field(
        ...,
        description="Contact identifier (email or phone) associated with this verification session",
    )
    otp: str = Field(..., description="One-time password for verification")
    action_type: VerificationActionType = Field(
        ..., description="Purpose of the verification session"
    )
    request_count: int = Field(..., description="Number of OTP send requests made")
    check_attempts: int = Field(..., description="Number of failed OTP validation attempts")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contact": "user@example.com",
                "otp": "847291",
                "action_type": "user_creation",
                "request_count": 1,
                "check_attempts": 0,
            }
        }
    )


class VerificationTokenData(BaseModel):
    contact: str = Field(..., description="Contact identifier verified by this token")
    action_type: VerificationActionType = Field(
        ..., description="Purpose of the verification token"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "contact": "user@example.com",
                "action_type": "user_creation",
            }
        }
    )
