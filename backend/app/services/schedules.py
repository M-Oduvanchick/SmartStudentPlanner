import asyncio
import hashlib
import re
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pnrpu import PnrpuExcelParser, ScheduleDocument
from app.models.schedule import Schedule
from app.models.user import User
from app.repositories.schedules import ScheduleRepository
from app.schemas.schedule import ScheduleImportRequest


class ScheduleSource(Protocol):
    async def search_documents(self, group_name: str) -> list[ScheduleDocument]: ...

    async def download_document(self, document: ScheduleDocument) -> bytes: ...


class ScheduleDocumentNotFoundError(Exception):
    pass


class ScheduleNotSelectedError(Exception):
    pass


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.schedules = ScheduleRepository(session)
        self.parser = PnrpuExcelParser()

    async def search_documents(
        self,
        group_name: str,
        source: ScheduleSource,
    ) -> list[ScheduleDocument]:
        return await source.search_documents(group_name)

    async def import_for_user(
        self,
        user: User,
        data: ScheduleImportRequest,
        source: ScheduleSource,
    ) -> Schedule:
        documents = await source.search_documents(data.group_name)
        requested_url = str(data.document_url)
        document = next((item for item in documents if item.url == requested_url), None)
        if document is None:
            raise ScheduleDocumentNotFoundError

        schedule = await self._download_and_synchronize(
            document=document,
            group_name=data.group_name,
            source=source,
        )
        user.schedule_id = schedule.id
        await self.session.commit()
        return schedule

    async def get_current(self, user: User) -> Schedule:
        if user.schedule_id is None:
            raise ScheduleNotSelectedError
        schedule = await self.schedules.get_full(user.schedule_id)
        if schedule is None:
            raise ScheduleNotSelectedError
        return schedule

    async def refresh_current(self, user: User, source: ScheduleSource) -> Schedule:
        schedule = await self.get_current(user)
        document = ScheduleDocument(
            title=schedule.document_title,
            url=schedule.source_url,
        )
        refreshed = await self._download_and_synchronize(
            document=document,
            group_name=schedule.group.name,
            source=source,
        )
        await self.session.commit()
        return refreshed

    async def clear_current(self, user: User) -> None:
        user.schedule_id = None
        await self.session.commit()

    async def _download_and_synchronize(
        self,
        *,
        document: ScheduleDocument,
        group_name: str,
        source: ScheduleSource,
    ) -> Schedule:
        content = await source.download_document(document)
        parsed = await asyncio.to_thread(
            self.parser.parse,
            content,
            group_name=group_name,
            source_url=document.url,
        )
        return await self.schedules.synchronize(
            document=document,
            parsed=parsed,
            normalized_group_name=self._normalize_group_name(parsed.group_name),
            source_hash=hashlib.sha256(content).hexdigest(),
            synced_at=datetime.now(UTC),
        )

    @staticmethod
    def _normalize_group_name(group_name: str) -> str:
        return re.sub(r"\s+", "", group_name).casefold().replace("ё", "е")
