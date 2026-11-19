from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[Task]:
        result = await self.session.execute(
            select(Task).where(Task.user_id == user_id).order_by(Task.due_at, Task.created_at)
        )
        return list(result.scalars().all())

    async def get_for_user(self, task_id: UUID, user_id: UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        title: str,
        description: str | None,
        due_at: datetime,
        reminder_at: datetime | None,
        priority: str,
    ) -> Task:
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            due_at=due_at,
            reminder_at=reminder_at,
            priority=priority,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update(self, task: Task, changes: Mapping[str, object]) -> Task:
        for field, value in changes.items():
            setattr(task, field, value)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
