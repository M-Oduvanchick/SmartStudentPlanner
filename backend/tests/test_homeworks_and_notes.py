from typing import Any
from uuid import uuid4

from httpx import AsyncClient


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


async def create_homework(
    client: AsyncClient,
    headers: dict[str, str],
    **overrides: object,
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "subject": "Mathematics",
        "description": "Solve exercises 1-10",
        "deadline": "2026-12-05T18:00:00Z",
        "priority": "medium",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/homeworks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def create_task(
    client: AsyncClient,
    headers: dict[str, str],
    **overrides: object,
) -> dict[str, Any]:
    payload: dict[str, object] = {
        "title": "Prepare for exam",
        "due_at": "2026-12-01T10:30:00Z",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def create_note(
    client: AsyncClient,
    headers: dict[str, str],
    **overrides: object,
) -> dict[str, Any]:
    payload: dict[str, object] = {"content": "Review the lecture notes"}
    payload.update(overrides)
    response = await client.post("/api/v1/notes", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def test_homeworks_require_authentication(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/homeworks")
    create_response = await client.post(
        "/api/v1/homeworks",
        json={
            "subject": "Mathematics",
            "description": "Exercises",
            "deadline": "2026-12-05T18:00:00Z",
        },
    )

    assert list_response.status_code == 401
    assert create_response.status_code == 401


async def test_homework_crud_and_deadline_ordering(client: AsyncClient) -> None:
    user, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    later = await create_homework(
        client,
        headers,
        subject="  Physics  ",
        description="  Read chapter 4  ",
        deadline="2026-12-10T18:00:00Z",
    )
    earlier = await create_homework(
        client,
        headers,
        subject="Mathematics",
        deadline="2026-12-02T18:00:00Z",
    )

    assert later["user_id"] == user["id"]
    assert later["subject"] == "Physics"
    assert later["description"] == "Read chapter 4"
    assert later["priority"] == "medium"
    assert later["is_completed"] is False

    list_response = await client.get("/api/v1/homeworks", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [earlier["id"], later["id"]]

    homework_path = f"/api/v1/homeworks/{earlier['id']}"
    update_response = await client.patch(
        homework_path,
        json={
            "description": "All exercises completed",
            "priority": "high",
            "is_completed": True,
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "All exercises completed"
    assert update_response.json()["priority"] == "high"
    assert update_response.json()["is_completed"] is True

    get_response = await client.get(homework_path, headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == earlier["id"]

    delete_response = await client.delete(homework_path, headers=headers)
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert (await client.get(homework_path, headers=headers)).status_code == 404


async def test_homework_is_private(client: AsyncClient) -> None:
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
    homework = await create_homework(client, owner_headers)
    homework_path = f"/api/v1/homeworks/{homework['id']}"

    get_response = await client.get(homework_path, headers=outsider_headers)
    update_response = await client.patch(
        homework_path,
        json={"is_completed": True},
        headers=outsider_headers,
    )
    delete_response = await client.delete(homework_path, headers=outsider_headers)

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    assert (await client.get(homework_path, headers=owner_headers)).status_code == 200


async def test_homework_input_is_validated(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )

    blank_subject_response = await client.post(
        "/api/v1/homeworks",
        json={
            "subject": "   ",
            "description": "Exercises",
            "deadline": "2026-12-05T18:00:00Z",
        },
        headers=headers,
    )
    naive_deadline_response = await client.post(
        "/api/v1/homeworks",
        json={
            "subject": "Mathematics",
            "description": "Exercises",
            "deadline": "2026-12-05T18:00:00",
        },
        headers=headers,
    )
    invalid_priority_response = await client.post(
        "/api/v1/homeworks",
        json={
            "subject": "Mathematics",
            "description": "Exercises",
            "deadline": "2026-12-05T18:00:00Z",
            "priority": "urgent",
        },
        headers=headers,
    )
    homework = await create_homework(client, headers)
    null_description_response = await client.patch(
        f"/api/v1/homeworks/{homework['id']}",
        json={"description": None},
        headers=headers,
    )

    assert blank_subject_response.status_code == 422
    assert naive_deadline_response.status_code == 422
    assert invalid_priority_response.status_code == 422
    assert null_description_response.status_code == 422


async def test_notes_require_authentication(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/notes")
    create_response = await client.post(
        "/api/v1/notes",
        json={"content": "Lecture note"},
    )

    assert list_response.status_code == 401
    assert create_response.status_code == 401


async def test_note_crud_and_user_isolation(client: AsyncClient) -> None:
    user, owner_headers = await authenticate(
        client,
        username="owner",
        email="owner@example.com",
    )
    _, outsider_headers = await authenticate(
        client,
        username="outsider",
        email="outsider@example.com",
    )
    note = await create_note(client, owner_headers, content="  Lecture summary  ")
    await create_note(client, outsider_headers, content="Outsider note")

    assert note["user_id"] == user["id"]
    assert note["content"] == "Lecture summary"
    assert note["task_id"] is None
    assert note["homework_id"] is None

    list_response = await client.get("/api/v1/notes", headers=owner_headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [note["id"]]

    note_path = f"/api/v1/notes/{note['id']}"
    assert (await client.get(note_path, headers=outsider_headers)).status_code == 404
    assert (
        await client.patch(
            note_path,
            json={"content": "Changed by outsider"},
            headers=outsider_headers,
        )
    ).status_code == 404
    assert (await client.delete(note_path, headers=outsider_headers)).status_code == 404

    update_response = await client.patch(
        note_path,
        json={"content": "Updated lecture summary"},
        headers=owner_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["content"] == "Updated lecture summary"

    delete_response = await client.delete(note_path, headers=owner_headers)
    assert delete_response.status_code == 204
    assert (await client.get(note_path, headers=owner_headers)).status_code == 404


async def test_note_can_switch_between_task_and_homework(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    task = await create_task(client, headers)
    homework = await create_homework(client, headers)

    note = await create_note(client, headers, task_id=task["id"])
    assert note["task_id"] == task["id"]
    assert note["homework_id"] is None

    update_response = await client.patch(
        f"/api/v1/notes/{note['id']}",
        json={"homework_id": homework["id"]},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["task_id"] is None
    assert update_response.json()["homework_id"] == homework["id"]


async def test_note_rejects_multiple_or_inaccessible_links(client: AsyncClient) -> None:
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
    homework = await create_homework(client, owner_headers)

    multiple_links_response = await client.post(
        "/api/v1/notes",
        json={
            "content": "Invalid note",
            "task_id": task["id"],
            "homework_id": homework["id"],
        },
        headers=owner_headers,
    )
    foreign_link_response = await client.post(
        "/api/v1/notes",
        json={"content": "Invalid note", "task_id": task["id"]},
        headers=outsider_headers,
    )
    missing_link_response = await client.post(
        "/api/v1/notes",
        json={"content": "Invalid note", "homework_id": str(uuid4())},
        headers=owner_headers,
    )

    assert multiple_links_response.status_code == 422
    assert foreign_link_response.status_code == 404
    assert missing_link_response.status_code == 404


async def test_note_survives_linked_item_deletion(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    task = await create_task(client, headers)
    note = await create_note(client, headers, task_id=task["id"])

    delete_response = await client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    note_response = await client.get(f"/api/v1/notes/{note['id']}", headers=headers)

    assert delete_response.status_code == 204
    assert note_response.status_code == 200
    assert note_response.json()["task_id"] is None


async def test_note_content_is_validated(client: AsyncClient) -> None:
    _, headers = await authenticate(
        client,
        username="student",
        email="student@example.com",
    )
    blank_content_response = await client.post(
        "/api/v1/notes",
        json={"content": "   "},
        headers=headers,
    )
    note = await create_note(client, headers)
    null_content_response = await client.patch(
        f"/api/v1/notes/{note['id']}",
        json={"content": None},
        headers=headers,
    )

    assert blank_content_response.status_code == 422
    assert null_content_response.status_code == 422
