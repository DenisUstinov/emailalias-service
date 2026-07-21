from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PasswordAttemptSessionData(BaseModel):
    failed_attempts: int = Field(
        ...,
        ge=0,
        description="Number of failed password verifications in current window",
    )
    window_start: datetime = Field(
        ...,
        description="Timestamp of first attempt in current rate-limit window (ISO 8601 UTC)",
    )
    blocked_until: datetime | None = Field(
        default=None,
        description="Timestamp until which verification is temporarily blocked (ISO 8601 UTC)",
    )
    last_block_ts: datetime | None = Field(
        default=None,
        description="Timestamp of last applied block for exponential backoff logic (ISO 8601 UTC)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "failed_attempts": 2,
                "window_start": "2026-01-15T10:30:00Z",
                "blocked_until": None,
                "last_block_ts": None,
            }
        }
    )
