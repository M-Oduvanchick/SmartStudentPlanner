from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.pnrpu.models import ParsedSchedule, ScheduleDocument
from app.models.schedule import Schedule, ScheduleLesson, StudyGroup


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_full(self, schedule_id: UUID) -> Schedule | None:
        result = await self.session.execute(
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .options(selectinload(Schedule.group), selectinload(Schedule.lessons))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_source_url(self, source_url: str) -> Schedule | None:
        result = await self.session.execute(
            select(Schedule).where(Schedule.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def get_or_create_group(self, name: str, normalized_name: str) -> StudyGroup:
        result = await self.session.execute(
            select(StudyGroup).where(StudyGroup.normalized_name == normalized_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            group = StudyGroup(name=name, normalized_name=normalized_name)
            self.session.add(group)
            await self.session.flush()
        elif group.name != name:
            group.name = name
        return group

    async def synchronize(
        self,
        *,
        document: ScheduleDocument,
        parsed: ParsedSchedule,
        normalized_group_name: str,
        source_hash: str,
        synced_at: datetime,
    ) -> Schedule:
        group = await self.get_or_create_group(parsed.group_name, normalized_group_name)
        schedule = await self.get_by_source_url(document.url)
        source_changed = schedule is None or schedule.source_hash != source_hash

        if schedule is None:
            schedule = Schedule(
                group_id=group.id,
                document_title=document.title,
                source_url=document.url,
                source_hash=source_hash,
                title=parsed.title,
                sheet_name=parsed.sheet_name,
                academic_year_start=parsed.academic_year_start,
                academic_year_end=parsed.academic_year_end,
                semester=parsed.semester.value,
                starts_on=parsed.starts_on,
                first_week_number=parsed.first_week_number,
                synced_at=synced_at,
            )
            self.session.add(schedule)
            await self.session.flush()
        else:
            schedule.group_id = group.id
            schedule.document_title = document.title
            schedule.source_hash = source_hash
            schedule.title = parsed.title
            schedule.sheet_name = parsed.sheet_name
            schedule.academic_year_start = parsed.academic_year_start
            schedule.academic_year_end = parsed.academic_year_end
            schedule.semester = parsed.semester.value
            schedule.starts_on = parsed.starts_on
            schedule.first_week_number = parsed.first_week_number
            schedule.synced_at = synced_at

        if source_changed:
            await self.session.execute(
                delete(ScheduleLesson).where(ScheduleLesson.schedule_id == schedule.id)
            )
            self.session.expire(schedule, ["lessons"])
            self.session.add_all(
                [
                    ScheduleLesson(
                        schedule_id=schedule.id,
                        ordinal=ordinal,
                        weekday=lesson.weekday,
                        start_time=lesson.start_time,
                        end_time=lesson.end_time,
                        week_pattern=lesson.week_pattern.value,
                        subject=lesson.subject,
                        lesson_type=lesson.lesson_type.value,
                        details=lesson.details,
                        teacher=lesson.teacher,
                        room=lesson.room,
                        building=lesson.building,
                        subgroup=lesson.subgroup,
                        raw_text=lesson.raw_text,
                    )
                    for ordinal, lesson in enumerate(parsed.lessons, start=1)
                ]
            )

        await self.session.flush()
        synchronized = await self.get_full(schedule.id)
        if synchronized is None:
            raise RuntimeError("Synchronized schedule disappeared")
        return synchronized
