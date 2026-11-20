from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.integrations.pnrpu.models import LessonType, Semester, WeekPattern


class ScheduleDocumentResponse(BaseModel):
    title: str
    url: HttpUrl
    filename: str


class ScheduleImportRequest(BaseModel):
    group_name: str = Field(min_length=2, max_length=100)
    document_url: HttpUrl

    @field_validator("group_name", mode="before")
    @classmethod
    def strip_group_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class StudyGroupResponse(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class ScheduleLessonResponse(BaseModel):
    id: UUID
    ordinal: int
    weekday: int
    start_time: time
    end_time: time
    week_pattern: WeekPattern
    subject: str
    lesson_type: LessonType
    details: str
    teacher: str | None
    room: str | None
    building: str | None
    subgroup: int | None
    raw_text: str

    model_config = ConfigDict(from_attributes=True)


class ScheduleResponse(BaseModel):
    id: UUID
    group: StudyGroupResponse
    document_title: str
    source_url: HttpUrl
    title: str
    sheet_name: str
    academic_year_start: int | None
    academic_year_end: int | None
    semester: Semester
    starts_on: date | None
    first_week_number: int | None
    synced_at: datetime
    updated_at: datetime
    lessons: list[ScheduleLessonResponse]

    model_config = ConfigDict(from_attributes=True)
