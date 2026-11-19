from datetime import date, time
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from app.integrations.pnrpu import (
    InvalidScheduleFileError,
    LessonType,
    PnrpuExcelParser,
    PnrpuScheduleClient,
    ScheduleDocument,
    ScheduleGroupNotFoundError,
    ScheduleParseError,
    ScheduleSourceError,
    Semester,
    WeekPattern,
)


def build_schedule_workbook() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Расписание"

    worksheet.merge_cells("A1:D1")
    worksheet["A1"] = "Осенний семестр 2026-2027 уч. года (до смены)"
    worksheet.merge_cells("A2:D2")
    worksheet["A2"] = "Начало занятий с 1 сентября - 1 неделя"
    worksheet["A3"] = "Дни"
    worksheet["B3"] = "Время"
    worksheet.merge_cells("C3:D3")
    worksheet["C3"] = "ИВТ -25-1б"

    worksheet.merge_cells("A4:A7")
    worksheet["A4"] = "п о н е д е л ь н и к"
    worksheet.merge_cells("B4:B5")
    worksheet["B4"] = "8:00"
    worksheet.merge_cells("C4:D5")
    worksheet["C4"] = "БАЗЫ ДАННЫХ (лек)\nдоц. Петров А.А. 402 к.А (ЭТФ)"

    worksheet.merge_cells("B6:B7")
    worksheet["B6"] = "9:40"
    worksheet.merge_cells("C6:D6")
    worksheet["C6"] = "ФИЗИКА (лаб)\nдоц. Иванова И.И. 246 гл."
    worksheet.merge_cells("C7:D7")
    worksheet["C7"] = "ФИЗИКА (пр)\nдоц. Иванова И.И. 248 гл."

    worksheet.merge_cells("A8:A9")
    worksheet["A8"] = "в т о р н и к"
    worksheet.merge_cells("B8:B9")
    worksheet["B8"] = time(11, 30)
    worksheet["C8"] = "ИНОСТРАННЫЙ ЯЗЫК (пр)\nдоц. Смирнова И.В. 409 к.А (ЭТФ)"
    worksheet["D8"] = "ИНОСТРАННЫЙ ЯЗЫК (пр)\nдоц. Орлова О.В. 410 к.А (ЭТФ)"

    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def build_malformed_workbook() -> bytes:
    workbook = Workbook()
    workbook.active["A1"] = "Not a schedule"
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


async def test_client_finds_only_unique_same_origin_xlsx_documents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/student/schedule/"
        assert request.url.params["search"] == "ИВТ-25-1б"
        return httpx.Response(
            200,
            text="""
                <a href="/upload/schedules/first file.xlsx"><span>До смены</span></a>
                <a href="/upload/schedules/first file.xlsx">Duplicate</a>
                <a href="/upload/schedules/second.xlsx"></a>
                <a href="/upload/schedules/calendar.pdf">PDF</a>
                <a href="https://example.com/external.xlsx">External</a>
            """,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = PnrpuScheduleClient(http_client=http_client)
        documents = await client.search_documents("  ИВТ-25-1б  ")

    assert documents == [
        ScheduleDocument(
            title="До смены",
            url="https://pstu.ru/upload/schedules/first%20file.xlsx",
        ),
        ScheduleDocument(
            title="second.xlsx",
            url="https://pstu.ru/upload/schedules/second.xlsx",
        ),
    ]
    assert documents[0].filename == "first file.xlsx"


async def test_client_downloads_valid_xlsx_with_size_limit() -> None:
    content = b"PK\x03\x04valid-xlsx-content"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/upload/schedule.xlsx"
        return httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = PnrpuScheduleClient(
            http_client=http_client,
            max_file_size_bytes=len(content),
        )
        result = await client.download_document(
            ScheduleDocument(
                title="Schedule",
                url="https://pstu.ru/upload/schedule.xlsx",
            )
        )

    assert result == content


@pytest.mark.parametrize(
    ("content", "max_size"),
    [
        (b"not-an-xlsx", 100),
        (b"PK\x03\x04too-large", 5),
    ],
)
async def test_client_rejects_invalid_or_oversized_files(
    content: bytes,
    max_size: int,
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=content))
    ) as http_client:
        client = PnrpuScheduleClient(
            http_client=http_client,
            max_file_size_bytes=max_size,
        )
        with pytest.raises(InvalidScheduleFileError):
            await client.download_document(
                ScheduleDocument(
                    title="Schedule",
                    url="https://pstu.ru/upload/schedule.xlsx",
                )
            )


async def test_client_rejects_external_document_without_request() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: pytest.fail("Unexpected request"))
    ) as http_client:
        client = PnrpuScheduleClient(http_client=http_client)
        with pytest.raises(InvalidScheduleFileError):
            await client.download_document(
                ScheduleDocument(
                    title="External",
                    url="https://example.com/schedule.xlsx",
                )
            )


async def test_client_wraps_source_http_errors() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503))
    ) as http_client:
        client = PnrpuScheduleClient(http_client=http_client)
        with pytest.raises(ScheduleSourceError):
            await client.search_documents("ИВТ-25-1б")
        with pytest.raises(ScheduleSourceError):
            await client.download_document(
                ScheduleDocument(
                    title="Schedule",
                    url="https://pstu.ru/upload/schedule.xlsx",
                )
            )


def test_parser_normalizes_schedule_metadata_and_lessons() -> None:
    source_url = "https://pstu.ru/upload/schedule.xlsx"

    schedule = PnrpuExcelParser().parse(
        build_schedule_workbook(),
        group_name=" ИВТ-25-1б ",
        source_url=source_url,
    )

    assert schedule.title == "Осенний семестр 2026-2027 уч. года (до смены)"
    assert schedule.sheet_name == "Расписание"
    assert schedule.group_name == "ИВТ-25-1б"
    assert schedule.academic_year_start == 2026
    assert schedule.academic_year_end == 2027
    assert schedule.semester == Semester.FALL
    assert schedule.starts_on == date(2026, 9, 1)
    assert schedule.first_week_number == 1
    assert schedule.source_url == source_url
    assert len(schedule.lessons) == 5

    every_week_lesson = schedule.lessons[0]
    assert every_week_lesson.weekday == 1
    assert every_week_lesson.start_time == time(8, 0)
    assert every_week_lesson.end_time == time(9, 30)
    assert every_week_lesson.week_pattern == WeekPattern.EVERY
    assert every_week_lesson.subject == "БАЗЫ ДАННЫХ"
    assert every_week_lesson.lesson_type == LessonType.LECTURE
    assert every_week_lesson.teacher == "доц. Петров А.А."
    assert every_week_lesson.room == "402 к.А"
    assert every_week_lesson.building == "ЭТФ"
    assert every_week_lesson.subgroup is None

    assert schedule.lessons[1].week_pattern == WeekPattern.ODD
    assert schedule.lessons[1].lesson_type == LessonType.LABORATORY
    assert schedule.lessons[2].week_pattern == WeekPattern.EVEN
    assert schedule.lessons[2].lesson_type == LessonType.PRACTICE
    assert {lesson.subgroup for lesson in schedule.lessons[3:]} == {1, 2}
    assert all(lesson.weekday == 2 for lesson in schedule.lessons[3:])


def test_parser_reports_missing_group() -> None:
    with pytest.raises(ScheduleGroupNotFoundError):
        PnrpuExcelParser().parse(
            build_schedule_workbook(),
            group_name="АСУ-25-1б",
        )


@pytest.mark.parametrize("content", [b"not-an-xlsx", build_malformed_workbook()])
def test_parser_rejects_invalid_workbooks(content: bytes) -> None:
    with pytest.raises(ScheduleParseError):
        PnrpuExcelParser().parse(content)
