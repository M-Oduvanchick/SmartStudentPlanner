from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.tasks import TaskRepository
from app.schemas.common import Priority
from app.schemas.task import TaskCreate, TaskUpdate


class TaskNotFoundError(Exception):
    pass


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)

    async def list(self, user_id: UUID) -> list[Task]:
        return await self.tasks.list_for_user(user_id)

    async def get(self, task_id: UUID, user_id: UUID) -> Task:
        task = await self.tasks.get_for_user(task_id, user_id)
        if task is None:
            raise TaskNotFoundError
        return task

    async def create(self, user_id: UUID, data: TaskCreate) -> Task:
        task = await self.tasks.create(
            user_id=user_id,
            title=data.title,
            description=data.description,
            due_at=data.due_at,
            reminder_at=data.reminder_at,
            priority=data.priority.value,
        )
        await self.session.commit()
        return task

    async def update(self, task_id: UUID, user_id: UUID, data: TaskUpdate) -> Task:
        task = await self.get(task_id, user_id)
        changes = data.model_dump(exclude_unset=True)
        if isinstance(changes.get("priority"), Priority):
            changes["priority"] = changes["priority"].value
        task = await self.tasks.update(task, changes)
        await self.session.commit()
        return task

    async def delete(self, task_id: UUID, user_id: UUID) -> None:
        task = await self.get(task_id, user_id)
        await self.tasks.delete(task)
        await self.session.commit()
