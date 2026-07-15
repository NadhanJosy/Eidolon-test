"""Add privacy-safe diagnostic events."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008_diagnostic_events"
down_revision = "0007_memory_forgetting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("safe_message", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_diagnostic_events_character_id"),
        "diagnostic_events",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_events_conversation_id"),
        "diagnostic_events",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_events_created_at"),
        "diagnostic_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_events_user_id"),
        "diagnostic_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_diagnostic_events_user_id"), table_name="diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_events_created_at"), table_name="diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_events_conversation_id"), table_name="diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_events_character_id"), table_name="diagnostic_events")
    op.drop_table("diagnostic_events")
