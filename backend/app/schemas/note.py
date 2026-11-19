from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    task_id: UUID | None = None
    homework_id: UUID | None = None

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_single_link(self) -> "NoteCreate":
        if self.task_id is not None and self.homework_id is not None:
            raise ValueError("A note can be linked to only one item")
        return self


class NoteUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    task_id: UUID | None = None
    homework_id: UUID | None = None

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("content")
    @classmethod
    def reject_null_content(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value

    @model_validator(mode="after")
    def validate_single_link(self) -> "NoteUpdate":
        if self.task_id is not None and self.homework_id is not None:
            raise ValueError("A note can be linked to only one item")
        return self


class NoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    task_id: UUID | None
    homework_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
