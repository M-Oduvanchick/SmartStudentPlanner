from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


async def authenticate(
    client: AsyncClient,
    *,
    username: str,
    email: str,
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


async def create_task(
    client: AsyncClient,
    headers: dict[str, str],
    **overrides: object,
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "title": "Prepare for exam",
        "description": "Review chapters 1-5",
        "due_at": "2026-12-01T10:30:00Z",
        "reminder_at": "2026-12-01T09:30:00Z",
        "priority": "medium",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_tasks_require_authentication(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/tasks")
    create_response = await client.post(
        "/api/v1/tasks",
        json={"title": "Task", "due_at": "2026-12-01T10:30:00Z"},
    )

    assert list_response.status_code == 401
    assert create_response.status_code == 401


async def test_create_task_assigns_current_user_and_defaults(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    user, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )

    response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "  Prepare for exam  ",
            "description": "Review chapters 1-5",
            "due_at": "2026-12-01T10:30:00Z",
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == user["id"]
    assert data["title"] == "Prepare for exam"
    assert data["priority"] == "medium"
    assert data["is_completed"] is False
    assert data["reminder_at"] is None

    task = (await session.execute(select(Task))).scalar_one()
    assert str(task.user_id) == user["id"]
    assert task.title == "Prepare for exam"


async def test_list_tasks_returns_only_current_users_tasks_in_due_date_order(
    client: AsyncClient,
) -> None:
    _, first_headers = await authenticate(
        client,
        username="first-student",
        email="first@example.com",
    )
    _, second_headers = await authenticate(
        client,
        username="second-student",
        email="second@example.com",
    )
    await create_task(
        client,
        first_headers,
        title="Later task",
        due_at="2026-12-10T10:30:00Z",
    )
    await create_task(
        client,
        first_headers,
        title="Earlier task",
        due_at="2026-12-02T10:30:00Z",
    )
    await create_task(client, second_headers, title="Another user's task")

    response = await client.get("/api/v1/tasks", headers=first_headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Earlier task", "Later task"]


async def test_task_can_be_read_updated_completed_and_deleted(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    task = await create_task(client, headers)
    task_path = f"/api/v1/tasks/{task['id']}"

    get_response = await client.get(task_path, headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == task["id"]

    update_response = await client.patch(
        task_path,
        json={
            "title": "Exam preparation complete",
            "description": None,
            "reminder_at": None,
            "priority": "high",
            "is_completed": True,
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_task = update_response.json()
    assert updated_task["title"] == "Exam preparation complete"
    assert updated_task["description"] is None
    assert updated_task["reminder_at"] is None
    assert updated_task["priority"] == "high"
    assert updated_task["is_completed"] is True

    delete_response = await client.delete(task_path, headers=headers)
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = await client.get(task_path, headers=headers)
    assert missing_response.status_code == 404


async def test_user_cannot_access_another_users_task(client: AsyncClient) -> None:
    _, owner_headers = await authenticate(
        client,
        username="owner",
        email="owner@example.com",
    )
    _, outsider_headers = await authenticate(
        client,
        username="outsider",
        email="outsider@example.com",
    )
    task = await create_task(client, owner_headers)
    task_path = f"/api/v1/tasks/{task['id']}"

    get_response = await client.get(task_path, headers=outsider_headers)
    update_response = await client.patch(
        task_path,
        json={"title": "Changed by outsider"},
        headers=outsider_headers,
    )
    delete_response = await client.delete(task_path, headers=outsider_headers)

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    owner_response = await client.get(task_path, headers=owner_headers)
    assert owner_response.status_code == 200
    assert owner_response.json()["title"] == "Prepare for exam"


async def test_task_input_is_validated(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )

    empty_title_response = await client.post(
        "/api/v1/tasks",
        json={"title": "   ", "due_at": "2026-12-01T10:30:00Z"},
        headers=headers,
    )
    invalid_priority_response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Task",
            "due_at": "2026-12-01T10:30:00Z",
            "priority": "urgent",
        },
        headers=headers,
    )
    missing_timezone_response = await client.post(
        "/api/v1/tasks",
        json={"title": "Task", "due_at": "2026-12-01T10:30:00"},
        headers=headers,
    )

    assert empty_title_response.status_code == 422
    assert invalid_priority_response.status_code == 422
    assert missing_timezone_response.status_code == 422


async def test_required_task_fields_cannot_be_cleared(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    task = await create_task(client, headers)

    response = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": None},
        headers=headers,
    )

    assert response.status_code == 422
