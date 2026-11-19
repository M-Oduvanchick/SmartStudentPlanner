from dataclasses import dataclass
from datetime import date, time
from enum import Enum
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse


@dataclass(frozen=True, slots=True)
class ScheduleDocument:
    title: str
    url: str

    @property
    def filename(self) -> str:
        path = PurePosixPath(unquote(urlparse(self.url).path))
        return path.name


class Semester(str, Enum):
    FALL = "fall"
    SPRING = "spring"
    UNKNOWN = "unknown"


class WeekPattern(str, Enum):
    EVERY = "every"
    ODD = "odd"
    EVEN = "even"


class LessonType(str, Enum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    LABORATORY = "laboratory"
    EXAM = "exam"
    CONSULTATION = "consultation"
    TEST = "test"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ParsedLesson:
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


@dataclass(frozen=True, slots=True)
class ParsedSchedule:
    title: str
    sheet_name: str
    group_name: str
    academic_year_start: int | None
    academic_year_end: int | None
    semester: Semester
    starts_on: date | None
    first_week_number: int | None
    lessons: tuple[ParsedLesson, ...]
    source_url: str | None = None
