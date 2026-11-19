import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet

from app.integrations.pnrpu.errors import ScheduleGroupNotFoundError, ScheduleParseError
from app.integrations.pnrpu.models import (
    LessonType,
    ParsedLesson,
    ParsedSchedule,
    Semester,
    WeekPattern,
)

_WEEKDAYS = {
    "понедельник": 1,
    "вторник": 2,
    "среда": 3,
    "четверг": 4,
    "пятница": 5,
    "суббота": 6,
    "воскресенье": 7,
}
_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_LESSON_TYPES = {
    "лек": LessonType.LECTURE,
    "лекция": LessonType.LECTURE,
    "пр": LessonType.PRACTICE,
    "прак": LessonType.PRACTICE,
    "практика": LessonType.PRACTICE,
    "лаб": LessonType.LABORATORY,
    "лабораторная": LessonType.LABORATORY,
    "экз": LessonType.EXAM,
    "экзамен": LessonType.EXAM,
    "конс": LessonType.CONSULTATION,
    "консультация": LessonType.CONSULTATION,
    "зач": LessonType.TEST,
    "зачет": LessonType.TEST,
    "зачёт": LessonType.TEST,
}
_ACADEMIC_YEAR_RE = re.compile(r"(?P<start>\d{4})\s*[-–]\s*(?P<end>\d{4})")
_START_DATE_RE = re.compile(
    r"\bс\s+(?P<day>\d{1,2})\s+(?P<month>[а-яё]+)",
    re.IGNORECASE,
)
_FIRST_WEEK_RE = re.compile(r"[-–]\s*(?P<week>\d+)\s+недел", re.IGNORECASE)
_TYPE_RE = re.compile(r"\((?P<type>[^()]{1,24})\)")
_ROOM_RE = re.compile(
    r"(?P<room>\d+[а-яёa-z]?(?:\s*(?:к\.\s*[а-яёa-z]|гл\.))?)"
    r"(?:\s*\((?P<building>[^()]+)\))?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _GroupColumns:
    name: str
    start_column: int
    end_column: int


class PnrpuExcelParser:
    def parse(
        self,
        content: bytes,
        *,
        group_name: str | None = None,
        source_url: str | None = None,
    ) -> ParsedSchedule:
        try:
            workbook = load_workbook(BytesIO(content), data_only=True, read_only=False)
        except (
            BadZipFile,
            InvalidFileException,
            KeyError,
            OSError,
            ParseError,
            ValueError,
        ) as error:
            raise ScheduleParseError("Failed to open the XLSX schedule") from error

        try:
            if not workbook.worksheets:
                raise ScheduleParseError("Schedule workbook has no worksheets")
            return self._parse_worksheet(
                workbook.worksheets[0],
                group_name=group_name,
                source_url=source_url,
            )
        finally:
            workbook.close()

    def _parse_worksheet(
        self,
        worksheet: Worksheet,
        *,
        group_name: str | None,
        source_url: str | None,
    ) -> ParsedSchedule:
        header_row, day_column, time_column = self._find_header(worksheet)
        merged_by_anchor = {
            (cell_range.min_row, cell_range.min_col): cell_range
            for cell_range in worksheet.merged_cells.ranges
        }
        groups = self._find_groups(worksheet, header_row, time_column, merged_by_anchor)
        group = self._select_group(groups, group_name)

        title = self._clean_text(worksheet.cell(1, 1).value)
        metadata_text = " ".join(
            self._clean_text(worksheet.cell(row, 1).value)
            for row in range(1, header_row)
            if worksheet.cell(row, 1).value is not None
        )
        academic_year_start, academic_year_end = self._parse_academic_year(metadata_text)
        semester = self._parse_semester(metadata_text)
        starts_on = self._parse_start_date(
            metadata_text,
            semester,
            academic_year_start,
            academic_year_end,
        )
        first_week_number = self._parse_first_week(metadata_text)
        lessons = self._parse_lessons(
            worksheet,
            header_row=header_row,
            day_column=day_column,
            time_column=time_column,
            group=group,
            merged_by_anchor=merged_by_anchor,
        )
        if not lessons:
            raise ScheduleParseError("No lessons found in the schedule worksheet")

        return ParsedSchedule(
            title=title,
            sheet_name=worksheet.title,
            group_name=group.name,
            academic_year_start=academic_year_start,
            academic_year_end=academic_year_end,
            semester=semester,
            starts_on=starts_on,
            first_week_number=first_week_number,
            lessons=tuple(lessons),
            source_url=source_url,
        )

    def _find_header(self, worksheet: Worksheet) -> tuple[int, int, int]:
        for row in range(1, min(worksheet.max_row, 15) + 1):
            headers = {
                self._normalize_label(worksheet.cell(row, column).value): column
                for column in range(1, worksheet.max_column + 1)
                if worksheet.cell(row, column).value is not None
            }
            if "дни" in headers and "время" in headers:
                return row, headers["дни"], headers["время"]
        raise ScheduleParseError("Schedule worksheet header was not found")

    def _find_groups(
        self,
        worksheet: Worksheet,
        header_row: int,
        time_column: int,
        merged_by_anchor: dict[tuple[int, int], object],
    ) -> list[_GroupColumns]:
        groups: list[_GroupColumns] = []
        for column in range(time_column + 1, worksheet.max_column + 1):
            cell = worksheet.cell(header_row, column)
            if isinstance(cell, MergedCell) or cell.value is None:
                continue
            merged_range = merged_by_anchor.get((header_row, column))
            end_column = getattr(merged_range, "max_col", column)
            groups.append(
                _GroupColumns(
                    name=self._clean_group_name(cell.value),
                    start_column=column,
                    end_column=end_column,
                )
            )
        if not groups:
            raise ScheduleParseError("No group columns found in the schedule worksheet")
        return groups

    def _select_group(
        self,
        groups: list[_GroupColumns],
        requested_group: str | None,
    ) -> _GroupColumns:
        if requested_group is None:
            if len(groups) != 1:
                raise ScheduleParseError(
                    "Workbook contains multiple groups; group_name is required"
                )
            return groups[0]

        normalized_group = self._normalize_group_name(requested_group)
        for group in groups:
            if self._normalize_group_name(group.name) == normalized_group:
                return group
        raise ScheduleGroupNotFoundError(f"Group {requested_group!r} was not found in the workbook")

    def _parse_lessons(
        self,
        worksheet: Worksheet,
        *,
        header_row: int,
        day_column: int,
        time_column: int,
        group: _GroupColumns,
        merged_by_anchor: dict[tuple[int, int], object],
    ) -> list[ParsedLesson]:
        lessons: list[ParsedLesson] = []
        weekday: int | None = None
        start_time: time | None = None
        slot_first_row: int | None = None
        slot_last_row: int | None = None

        for row in range(header_row + 1, worksheet.max_row + 1):
            day_value = worksheet.cell(row, day_column).value
            parsed_weekday = self._parse_weekday(day_value)
            if parsed_weekday is not None:
                weekday = parsed_weekday
                start_time = None
                slot_first_row = None
                slot_last_row = None

            time_cell = worksheet.cell(row, time_column)
            parsed_time = self._parse_time(time_cell.value)
            if parsed_time is not None:
                start_time = parsed_time
                slot_first_row = row
                time_range = merged_by_anchor.get((row, time_column))
                slot_last_row = getattr(time_range, "max_row", row + 1)

            if (
                weekday is None
                or start_time is None
                or slot_first_row is None
                or slot_last_row is None
                or row > slot_last_row
            ):
                continue

            for column in range(group.start_column, group.end_column + 1):
                cell = worksheet.cell(row, column)
                if isinstance(cell, MergedCell) or cell.value is None:
                    continue
                raw_text = self._clean_multiline_text(cell.value)
                if not raw_text:
                    continue

                merged_range = merged_by_anchor.get((row, column))
                lesson_first_row = getattr(merged_range, "min_row", row)
                lesson_last_row = getattr(merged_range, "max_row", row)
                lesson_first_column = getattr(merged_range, "min_col", column)
                lesson_last_column = getattr(merged_range, "max_col", column)
                week_pattern = self._week_pattern(
                    lesson_first_row,
                    lesson_last_row,
                    slot_first_row,
                    slot_last_row,
                )
                subgroup = self._subgroup(
                    group,
                    lesson_first_column,
                    lesson_last_column,
                )
                subject, lesson_type, details, teacher, room, building = self._parse_lesson_text(
                    raw_text
                )
                lessons.append(
                    ParsedLesson(
                        weekday=weekday,
                        start_time=start_time,
                        end_time=self._lesson_end_time(start_time),
                        week_pattern=week_pattern,
                        subject=subject,
                        lesson_type=lesson_type,
                        details=details,
                        teacher=teacher,
                        room=room,
                        building=building,
                        subgroup=subgroup,
                        raw_text=raw_text,
                    )
                )
        return lessons

    def _parse_lesson_text(
        self,
        raw_text: str,
    ) -> tuple[str, LessonType, str, str | None, str | None, str | None]:
        type_match = _TYPE_RE.search(raw_text)
        if type_match is None:
            return self._collapse_whitespace(raw_text), LessonType.OTHER, "", None, None, None

        subject = self._collapse_whitespace(raw_text[: type_match.start()])
        type_label = self._normalize_label(type_match.group("type"))
        lesson_type = _LESSON_TYPES.get(type_label, LessonType.OTHER)
        details = self._clean_multiline_text(raw_text[type_match.end() :])
        detail_lines = [line for line in details.splitlines() if line]
        if len(detail_lines) != 1:
            return subject, lesson_type, details, None, None, None

        detail_line = detail_lines[0]
        room_match = _ROOM_RE.search(detail_line)
        if room_match is None:
            return subject, lesson_type, details, detail_line or None, None, None

        teacher = detail_line[: room_match.start()].strip(" ,;") or None
        room = self._collapse_whitespace(room_match.group("room"))
        building_value = room_match.group("building")
        building = self._collapse_whitespace(building_value) if building_value else None
        return subject, lesson_type, details, teacher, room, building

    @staticmethod
    def _week_pattern(
        lesson_first_row: int,
        lesson_last_row: int,
        slot_first_row: int,
        slot_last_row: int,
    ) -> WeekPattern:
        if lesson_first_row <= slot_first_row and lesson_last_row >= slot_last_row:
            return WeekPattern.EVERY
        if lesson_first_row == slot_first_row:
            return WeekPattern.ODD
        return WeekPattern.EVEN

    @staticmethod
    def _subgroup(
        group: _GroupColumns,
        lesson_first_column: int,
        lesson_last_column: int,
    ) -> int | None:
        if group.start_column == group.end_column or (
            lesson_first_column <= group.start_column and lesson_last_column >= group.end_column
        ):
            return None
        return lesson_first_column - group.start_column + 1

    @staticmethod
    def _parse_academic_year(text: str) -> tuple[int | None, int | None]:
        match = _ACADEMIC_YEAR_RE.search(text)
        if match is None:
            return None, None
        return int(match.group("start")), int(match.group("end"))

    @staticmethod
    def _parse_semester(text: str) -> Semester:
        normalized = text.casefold()
        if "осенн" in normalized:
            return Semester.FALL
        if "весенн" in normalized:
            return Semester.SPRING
        return Semester.UNKNOWN

    @staticmethod
    def _parse_start_date(
        text: str,
        semester: Semester,
        academic_year_start: int | None,
        academic_year_end: int | None,
    ) -> date | None:
        match = _START_DATE_RE.search(text)
        if match is None:
            return None
        month = _MONTHS.get(match.group("month").casefold())
        if month is None:
            return None
        year = academic_year_end if semester == Semester.SPRING else academic_year_start
        if year is None:
            return None
        try:
            return date(year, month, int(match.group("day")))
        except ValueError:
            return None

    @staticmethod
    def _parse_first_week(text: str) -> int | None:
        match = _FIRST_WEEK_RE.search(text)
        return int(match.group("week")) if match is not None else None

    @staticmethod
    def _parse_weekday(value: object) -> int | None:
        normalized = re.sub(r"\s+", "", str(value or "")).casefold().replace("ё", "е")
        return _WEEKDAYS.get(normalized)

    @staticmethod
    def _parse_time(value: object) -> time | None:
        if isinstance(value, time):
            return value.replace(second=0, microsecond=0)
        if isinstance(value, datetime):
            return value.time().replace(second=0, microsecond=0)
        if isinstance(value, (int, float)) and 0 <= value < 1:
            minutes = round(value * 24 * 60)
            return time(hour=minutes // 60, minute=minutes % 60)
        if isinstance(value, str):
            match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value)
            if match is not None:
                try:
                    return time(hour=int(match.group(1)), minute=int(match.group(2)))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _lesson_end_time(start_time: time) -> time:
        start = datetime.combine(date.min, start_time)
        return (start + timedelta(minutes=90)).time()

    @staticmethod
    def _clean_group_name(value: object) -> str:
        text = PnrpuExcelParser._clean_text(value)
        return re.sub(r"\s*-\s*", "-", text)

    @staticmethod
    def _normalize_group_name(value: object) -> str:
        return re.sub(r"\s+", "", str(value)).casefold().replace("ё", "е")

    @staticmethod
    def _normalize_label(value: object) -> str:
        return PnrpuExcelParser._collapse_whitespace(value).casefold().replace("ё", "е")

    @staticmethod
    def _clean_text(value: object) -> str:
        return PnrpuExcelParser._collapse_whitespace(value)

    @staticmethod
    def _clean_multiline_text(value: object) -> str:
        text = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        lines = [PnrpuExcelParser._collapse_whitespace(line) for line in text.split("\n")]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _collapse_whitespace(value: object) -> str:
        return " ".join(str(value or "").replace("\xa0", " ").split())
