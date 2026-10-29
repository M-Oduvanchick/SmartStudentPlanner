from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

UserFactory = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


@pytest.fixture
def registered_user() -> UserFactory:
    async def create(
        client: AsyncClient,
        *,
        username: str = "student",
        email: str = "student@example.com",
        password: str = "secure-password",
    ) -> dict[str, Any]:
        response = await client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert response.status_code == 201
        return response.json()

    return create


async def test_register_creates_user_without_exposing_password(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "Student.User",
            "email": "Student@Example.com",
            "password": "secure-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "student.user"
    assert response.json()["email"] == "student@example.com"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()

    user = (await session.execute(select(User))).scalar_one()
    assert user.password_hash != "secure-password"
    assert user.password_hash.startswith("$argon2")


async def test_register_rejects_empty_password(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "student", "email": "student@example.com", "password": ""},
    )

    assert response.status_code == 422
    user_count = await session.scalar(select(func.count()).select_from(User))
    assert user_count == 0


@pytest.mark.parametrize(
    ("username", "email"),
    [
        ("student", "another@example.com"),
        ("another", "student@example.com"),
    ],
)
async def test_register_rejects_duplicate_username_or_email(
    client: AsyncClient,
    session: AsyncSession,
    registered_user: UserFactory,
    username: str,
    email: str,
) -> None:
    await registered_user(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "another-password"},
    )

    assert response.status_code == 409
    user_count = await session.scalar(select(func.count()).select_from(User))
    assert user_count == 1


@pytest.mark.parametrize("identifier", ["student", "student@example.com"])
async def test_login_accepts_username_or_email(
    client: AsyncClient,
    registered_user: UserFactory,
    identifier: str,
) -> None:
    await registered_user(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": "secure-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_login_rejects_wrong_password(
    client: AsyncClient,
    registered_user: UserFactory,
) -> None:
    await registered_user(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "student", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_current_user_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401


async def test_current_user_returns_token_owner(
    client: AsyncClient,
    registered_user: UserFactory,
) -> None:
    user = await registered_user(client)
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "student", "password": "secure-password"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == "student@example.com"


async def test_current_user_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
