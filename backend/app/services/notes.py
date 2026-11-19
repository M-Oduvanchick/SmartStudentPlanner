from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.repositories.homeworks import HomeworkRepository
from app.repositories.notes import NoteRepository
from app.repositories.tasks import TaskRepository
from app.schemas.note import NoteCreate, NoteUpdate


class NoteNotFoundError(Exception):
    pass


class NoteTargetNotFoundError(Exception):
    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(f"Linked {target} not found")


class NoteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notes = NoteRepository(session)
        self.tasks = TaskRepository(session)
        self.homeworks = HomeworkRepository(session)

    async def list(self, user_id: UUID) -> list[Note]:
        return await self.notes.list_for_user(user_id)

    async def get(self, note_id: UUID, user_id: UUID) -> Note:
        note = await self.notes.get_for_user(note_id, user_id)
        if note is None:
            raise NoteNotFoundError
        return note

    async def create(self, user_id: UUID, data: NoteCreate) -> Note:
        await self._validate_targets(user_id, data.task_id, data.homework_id)
        note = await self.notes.create(
            user_id=user_id,
            content=data.content,
            task_id=data.task_id,
            homework_id=data.homework_id,
        )
        await self.session.commit()
        return note

    async def update(self, note_id: UUID, user_id: UUID, data: NoteUpdate) -> Note:
        note = await self.get(note_id, user_id)
        changes = data.model_dump(exclude_unset=True)

        task_id = changes.get("task_id")
        homework_id = changes.get("homework_id")
        if task_id is not None:
            await self._validate_targets(user_id, task_id, None)
            changes["homework_id"] = None
        elif homework_id is not None:
            await self._validate_targets(user_id, None, homework_id)
            changes["task_id"] = None

        note = await self.notes.update(note, changes)
        await self.session.commit()
        return note

    async def delete(self, note_id: UUID, user_id: UUID) -> None:
        note = await self.get(note_id, user_id)
        await self.notes.delete(note)
        await self.session.commit()

    async def _validate_targets(
        self,
        user_id: UUID,
        task_id: UUID | None,
        homework_id: UUID | None,
    ) -> None:
        if task_id is not None:
            task = await self.tasks.get_for_user(task_id, user_id)
            if task is None:
                raise NoteTargetNotFoundError("task")
        if homework_id is not None:
            homework = await self.homeworks.get_for_user(homework_id, user_id)
            if homework is None:
                raise NoteTargetNotFoundError("homework")
