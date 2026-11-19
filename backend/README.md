# Smart Student Planner Backend

Backend реализован на FastAPI, SQLAlchemy и PostgreSQL. Текущий этап включает
регистрацию, вход по username или email, JWT-аутентификацию и CRUD личных задач.

## Запуск через Docker Compose

Из корня репозитория:

```bash
JWT_SECRET_KEY="replace-with-a-random-secret-at-least-32-characters" docker compose up --build
```

После запуска доступны:

- API: <http://localhost:8000>;
- Swagger UI: <http://localhost:8000/docs>;
- health check: <http://localhost:8000/health>.

Миграции применяются автоматически перед запуском backend.

## Локальная разработка

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Проверки:

```bash
pytest
ruff check .
ruff format --check .
```

## REST API

- `POST /api/v1/auth/register` - регистрация;
- `POST /api/v1/auth/login` - получение JWT access token;
- `GET /api/v1/users/me` - данные авторизованного пользователя;
- `POST /api/v1/tasks` - создание задачи;
- `GET /api/v1/tasks` - список задач текущего пользователя;
- `GET /api/v1/tasks/{task_id}` - получение задачи;
- `PATCH /api/v1/tasks/{task_id}` - изменение задачи и отметка выполнения;
- `DELETE /api/v1/tasks/{task_id}` - удаление задачи;
- `GET /health` - проверка доступности приложения.

Все методы `/api/v1/tasks` требуют Bearer-токен. Даты `due_at` и `reminder_at`
передаются в ISO 8601 с часовым поясом, например `2026-12-01T10:30:00+05:00`.
