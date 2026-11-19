from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.homework import Homework


class HomeworkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[Homework]:
        result = await self.session.execute(
            select(Homework)
            .where(Homework.user_id == user_id)
            .order_by(Homework.deadline, Homework.created_at)
        )
        return list(result.scalars().all())

    async def get_for_user(self, homework_id: UUID, user_id: UUID) -> Homework | None:
        result = await self.session.execute(
            select(Homework).where(
                Homework.id == homework_id,
                Homework.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        subject: str,
        description: str,
        deadline: datetime,
        priority: str,
    ) -> Homework:
        homework = Homework(
            user_id=user_id,
            subject=subject,
            description=description,
            deadline=deadline,
            priority=priority,
        )
        self.session.add(homework)
        await self.session.flush()
        await self.session.refresh(homework)
        return homework

    async def update(self, homework: Homework, changes: Mapping[str, object]) -> Homework:
        for field, value in changes.items():
            setattr(homework, field, value)
        await self.session.flush()
        await self.session.refresh(homework)
        return homework

    async def delete(self, homework: Homework) -> None:
        await self.session.delete(homework)
