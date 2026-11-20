"""Create schedule storage.

Revision ID: 20261119_0005
Revises: 20261119_0004
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261119_0005"
down_revision: str | None = "20261119_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_study_groups"),
        sa.UniqueConstraint("normalized_name", name="uq_study_groups_normalized_name"),
    )
    op.create_table(
        "schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_title", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("sheet_name", sa.String(length=100), nullable=False),
        sa.Column("academic_year_start", sa.SmallInteger(), nullable=True),
        sa.Column("academic_year_end", sa.SmallInteger(), nullable=True),
        sa.Column("semester", sa.String(length=20), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("first_week_number", sa.SmallInteger(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "semester IN ('fall', 'spring', 'unknown')",
            name="ck_schedules_semester",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["study_groups.id"],
            name="fk_schedules_group_id_study_groups",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedules"),
        sa.UniqueConstraint("source_url", name="uq_schedules_source_url"),
    )
    op.create_index("ix_schedules_group_id", "schedules", ["group_id"], unique=False)
    op.create_table(
        "schedule_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("week_pattern", sa.String(length=10), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("lesson_type", sa.String(length=20), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("teacher", sa.String(length=500), nullable=True),
        sa.Column("room", sa.String(length=100), nullable=True),
        sa.Column("building", sa.String(length=100), nullable=True),
        sa.Column("subgroup", sa.SmallInteger(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "lesson_type IN "
            "('lecture', 'practice', 'laboratory', 'exam', 'consultation', 'test', 'other')",
            name="ck_schedule_lessons_lesson_type",
        ),
        sa.CheckConstraint(
            "week_pattern IN ('every', 'odd', 'even')",
            name="ck_schedule_lessons_week_pattern",
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 1 AND 7",
            name="ck_schedule_lessons_weekday",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            name="fk_schedule_lessons_schedule_id_schedules",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_lessons"),
        sa.UniqueConstraint(
            "schedule_id",
            "ordinal",
            name="uq_schedule_lessons_schedule_ordinal",
        ),
    )
    op.create_index(
        "ix_schedule_lessons_schedule_weekday_time",
        "schedule_lessons",
        ["schedule_id", "weekday", "start_time"],
        unique=False,
    )
    op.add_column(
        "users",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_schedule_id_schedules",
        "users",
        "schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_schedule_id", "users", ["schedule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_schedule_id", table_name="users")
    op.drop_constraint("fk_users_schedule_id_schedules", "users", type_="foreignkey")
    op.drop_column("users", "schedule_id")
    op.drop_index(
        "ix_schedule_lessons_schedule_weekday_time",
        table_name="schedule_lessons",
    )
    op.drop_table("schedule_lessons")
    op.drop_index("ix_schedules_group_id", table_name="schedules")
    op.drop_table("schedules")
    op.drop_table("study_groups")
