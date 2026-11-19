from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Priority


class HomeworkCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    deadline: AwareDatetime
    priority: Priority = Priority.MEDIUM

    @field_validator("subject", "description", mode="before")
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class HomeworkUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    deadline: AwareDatetime | None = None
    priority: Priority | None = None
    is_completed: bool | None = None

    @field_validator("subject", "description", mode="before")
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("subject", "description", "deadline", "priority", "is_completed")
    @classmethod
    def reject_null_for_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class HomeworkResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject: str
    description: str
    deadline: datetime
    priority: Priority
    is_completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
