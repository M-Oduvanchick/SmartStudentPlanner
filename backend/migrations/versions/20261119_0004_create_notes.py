"""Create notes table.

Revision ID: 20261119_0004
Revises: 20261119_0003
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261119_0004"
down_revision: str | None = "20261119_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("homework_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            "task_id IS NULL OR homework_id IS NULL",
            name="ck_notes_single_link",
        ),
        sa.ForeignKeyConstraint(
            ["homework_id"],
            ["homeworks.id"],
            name="fk_notes_homework_id_homeworks",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_notes_task_id_tasks",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notes_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index("ix_notes_homework_id", "notes", ["homework_id"], unique=False)
    op.create_index("ix_notes_task_id", "notes", ["task_id"], unique=False)
    op.create_index(
        "ix_notes_user_id_updated_at",
        "notes",
        ["user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notes_user_id_updated_at", table_name="notes")
    op.drop_index("ix_notes_task_id", table_name="notes")
    op.drop_index("ix_notes_homework_id", table_name="notes")
    op.drop_table("notes")
