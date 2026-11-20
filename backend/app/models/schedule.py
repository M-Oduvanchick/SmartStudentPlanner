from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudyGroup(Base):
    __tablename__ = "study_groups"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint(
            "semester IN ('fall', 'spring', 'unknown')",
            name="ck_schedules_semester",
        ),
        Index("ix_schedules_group_id", "group_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    group_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("study_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year_start: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    academic_year_end: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_week_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    group: Mapped[StudyGroup] = relationship(lazy="raise")
    lessons: Mapped[list["ScheduleLesson"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleLesson.ordinal",
        lazy="raise",
    )


class ScheduleLesson(Base):
    __tablename__ = "schedule_lessons"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_schedule_lessons_weekday"),
        CheckConstraint(
            "week_pattern IN ('every', 'odd', 'even')",
            name="ck_schedule_lessons_week_pattern",
        ),
        CheckConstraint(
            "lesson_type IN "
            "('lecture', 'practice', 'laboratory', 'exam', 'consultation', 'test', 'other')",
            name="ck_schedule_lessons_lesson_type",
        ),
        UniqueConstraint("schedule_id", "ordinal", name="uq_schedule_lessons_schedule_ordinal"),
        Index(
            "ix_schedule_lessons_schedule_weekday_time",
            "schedule_id",
            "weekday",
            "start_time",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    week_pattern: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    lesson_type: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    teacher: Mapped[str | None] = mapped_column(String(500), nullable=True)
    room: Mapped[str | None] = mapped_column(String(100), nullable=True)
    building: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subgroup: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    schedule: Mapped[Schedule] = relationship(back_populates="lessons", lazy="raise")
