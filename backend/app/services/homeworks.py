from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.homework import Homework
from app.repositories.homeworks import HomeworkRepository
from app.schemas.common import Priority
from app.schemas.homework import HomeworkCreate, HomeworkUpdate


class HomeworkNotFoundError(Exception):
    pass


class HomeworkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.homeworks = HomeworkRepository(session)

    async def list(self, user_id: UUID) -> list[Homework]:
        return await self.homeworks.list_for_user(user_id)

    async def get(self, homework_id: UUID, user_id: UUID) -> Homework:
        homework = await self.homeworks.get_for_user(homework_id, user_id)
        if homework is None:
            raise HomeworkNotFoundError
        return homework

    async def create(self, user_id: UUID, data: HomeworkCreate) -> Homework:
        homework = await self.homeworks.create(
            user_id=user_id,
            subject=data.subject,
            description=data.description,
            deadline=data.deadline,
            priority=data.priority.value,
        )
        await self.session.commit()
        return homework

    async def update(
        self,
        homework_id: UUID,
        user_id: UUID,
        data: HomeworkUpdate,
    ) -> Homework:
        homework = await self.get(homework_id, user_id)
        changes = data.model_dump(exclude_unset=True)
        if isinstance(changes.get("priority"), Priority):
            changes["priority"] = changes["priority"].value
        homework = await self.homeworks.update(homework, changes)
        await self.session.commit()
        return homework

    async def delete(self, homework_id: UUID, user_id: UUID) -> None:
        homework = await self.get(homework_id, user_id)
        await self.homeworks.delete(homework)
        await self.session.commit()
