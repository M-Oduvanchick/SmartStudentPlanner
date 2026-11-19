from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


class NoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[Note]:
        result = await self.session.execute(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.updated_at.desc(), Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, note_id: UUID, user_id: UUID) -> Note | None:
        result = await self.session.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: UUID,
        content: str,
        task_id: UUID | None,
        homework_id: UUID | None,
    ) -> Note:
        note = Note(
            user_id=user_id,
            content=content,
            task_id=task_id,
            homework_id=homework_id,
        )
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update(self, note: Note, changes: Mapping[str, object]) -> Note:
        for field, value in changes.items():
            setattr(note, field, value)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        await self.session.delete(note)
