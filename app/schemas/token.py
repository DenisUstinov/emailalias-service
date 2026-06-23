from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenData(BaseModel):
    user_id: UUID = Field(..., description="Unique identifier of the user")
    role: str = Field(..., description="User role for authorization decisions")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "user",
            }
        }
    )
