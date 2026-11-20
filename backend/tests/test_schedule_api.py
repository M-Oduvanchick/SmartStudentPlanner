from io import BytesIO
from typing import Any

from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_pnrpu_schedule_client
from app.integrations.pnrpu import ScheduleDocument, ScheduleSourceError
from app.main import app
from app.models.schedule import Schedule, ScheduleLesson, StudyGroup

DOCUMENT_URL = "https://pstu.ru/upload/schedule.xlsx"


class FakeScheduleSource:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.documents = [ScheduleDocument(title="До смены", url=DOCUMENT_URL)]
        self.search_error = False
        self.download_count = 0
        self.searched_groups: list[str] = []

    async def search_documents(self, group_name: str) -> list[ScheduleDocument]:
        if self.search_error:
            raise ScheduleSourceError("Source unavailable")
        self.searched_groups.append(group_name)
        return self.documents

    async def download_document(self, document: ScheduleDocument) -> bytes:
        assert document in self.documents
        self.download_count += 1
        return self.content


def build_schedule_workbook(subject: str = "БАЗЫ ДАННЫХ") -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Расписание"
    worksheet.merge_cells("A1:D1")
    worksheet["A1"] = "Осенний семестр 2026-2027 уч. года"
    worksheet.merge_cells("A2:D2")
    worksheet["A2"] = "Начало занятий с 1 сентября - 1 неделя"
    worksheet["A3"] = "Дни"
    worksheet["B3"] = "Время"
    worksheet.merge_cells("C3:D3")
    worksheet["C3"] = "ИВТ -25-1б"
    worksheet.merge_cells("A4:A5")
    worksheet["A4"] = "п о н е д е л ь н и к"
    worksheet.merge_cells("B4:B5")
    worksheet["B4"] = "8:00"
    worksheet.merge_cells("C4:D5")
    worksheet["C4"] = f"{subject} (лек)\nдоц. Петров А.А. 402 к.А (ЭТФ)"

    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


async def authenticate(
    client: AsyncClient,
    *,
    username: str = "student",
    email: str = "student@example.com",
) -> tuple[dict[str, Any], dict[str, str]]:
    password = "secure-password"
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": username, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return register_response.json(), {"Authorization": f"Bearer {token}"}


def use_schedule_source(source: FakeScheduleSource) -> None:
    app.dependency_overrides[get_pnrpu_schedule_client] = lambda: source


async def import_schedule(
    client: AsyncClient,
    headers: dict[str, str],
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/schedule/import",
        json={"group_name": "ИВТ-25-1б", "document_url": DOCUMENT_URL},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


async def test_schedule_endpoints_require_authentication(client: AsyncClient) -> None:
    documents_response = await client.get(
        "/api/v1/schedule/documents",
        params={"group_name": "ИВТ-25-1б"},
    )
    current_response = await client.get("/api/v1/schedule")

    assert documents_response.status_code == 401
    assert current_response.status_code == 401


async def test_search_schedule_documents(client: AsyncClient) -> None:
    _, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)

    response = await client.get(
        "/api/v1/schedule/documents",
        params={"group_name": "ИВТ-25-1б"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "До смены",
            "url": DOCUMENT_URL,
            "filename": "schedule.xlsx",
        }
    ]
    assert source.searched_groups == ["ИВТ-25-1б"]


async def test_import_persists_and_selects_schedule(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    user, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)

    schedule = await import_schedule(client, headers)

    assert schedule["group"]["name"] == "ИВТ-25-1б"
    assert schedule["document_title"] == "До смены"
    assert schedule["semester"] == "fall"
    assert schedule["starts_on"] == "2026-09-01"
    assert len(schedule["lessons"]) == 1
    assert schedule["lessons"][0]["subject"] == "БАЗЫ ДАННЫХ"
    assert schedule["lessons"][0]["week_pattern"] == "every"

    current_response = await client.get("/api/v1/schedule", headers=headers)
    me_response = await client.get("/api/v1/users/me", headers=headers)
    assert current_response.status_code == 200
    assert current_response.json()["id"] == schedule["id"]
    assert me_response.json()["id"] == user["id"]
    assert me_response.json()["schedule_id"] == schedule["id"]

    assert await session.scalar(select(func.count()).select_from(StudyGroup)) == 1
    assert await session.scalar(select(func.count()).select_from(Schedule)) == 1
    assert await session.scalar(select(func.count()).select_from(ScheduleLesson)) == 1


async def test_import_rejects_document_not_returned_by_search(client: AsyncClient) -> None:
    _, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)

    response = await client.post(
        "/api/v1/schedule/import",
        json={
            "group_name": "ИВТ-25-1б",
            "document_url": "https://pstu.ru/upload/another.xlsx",
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert source.download_count == 0


async def test_schedule_selection_is_per_user(client: AsyncClient) -> None:
    _, first_headers = await authenticate(client)
    _, second_headers = await authenticate(
        client,
        username="second-student",
        email="second@example.com",
    )
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)
    await import_schedule(client, first_headers)

    first_response = await client.get("/api/v1/schedule", headers=first_headers)
    second_response = await client.get("/api/v1/schedule", headers=second_headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 404


async def test_refresh_replaces_lessons_only_when_source_changes(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    _, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)
    imported = await import_schedule(client, headers)
    original_lesson_id = imported["lessons"][0]["id"]

    source.content = build_schedule_workbook("ДИСКРЕТНАЯ МАТЕМАТИКА")
    changed_response = await client.post("/api/v1/schedule/refresh", headers=headers)
    assert changed_response.status_code == 200
    changed = changed_response.json()
    assert changed["lessons"][0]["subject"] == "ДИСКРЕТНАЯ МАТЕМАТИКА"
    assert changed["lessons"][0]["id"] != original_lesson_id
    changed_lesson_id = changed["lessons"][0]["id"]
    assert await session.scalar(select(func.count()).select_from(ScheduleLesson)) == 1

    unchanged_response = await client.post("/api/v1/schedule/refresh", headers=headers)
    assert unchanged_response.status_code == 200
    assert unchanged_response.json()["lessons"][0]["id"] == changed_lesson_id


async def test_clear_schedule_removes_only_user_selection(client: AsyncClient) -> None:
    _, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    use_schedule_source(source)
    await import_schedule(client, headers)

    clear_response = await client.delete("/api/v1/schedule", headers=headers)
    current_response = await client.get("/api/v1/schedule", headers=headers)

    assert clear_response.status_code == 204
    assert current_response.status_code == 404


async def test_schedule_source_errors_return_bad_gateway(client: AsyncClient) -> None:
    _, headers = await authenticate(client)
    source = FakeScheduleSource(build_schedule_workbook())
    source.search_error = True
    use_schedule_source(source)

    response = await client.get(
        "/api/v1/schedule/documents",
        params={"group_name": "ИВТ-25-1б"},
        headers=headers,
    )

    assert response.status_code == 502
