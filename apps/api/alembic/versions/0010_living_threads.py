"""Add first-class living continuity threads."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010_living_threads"
down_revision = "0009_companion_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "continuity_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column("salience", sa.Float(), server_default="0.6", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.8", nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("last_referenced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_proactive_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
            "thread_kind IN ('follow_up', 'plan', 'promise', 'repair', 'ritual')",
            name="ck_continuity_threads_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_continuity_threads_status",
        ),
        sa.CheckConstraint(
            "salience >= 0 AND salience <= 1",
            name="ck_continuity_threads_salience",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_continuity_threads_confidence",
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_continuity_threads_user_id",
        "continuity_threads",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_character_id",
        "continuity_threads",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_conversation_id",
        "continuity_threads",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_source_message_id",
        "continuity_threads",
        ["source_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_status",
        "continuity_threads",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_dedupe_key",
        "continuity_threads",
        ["dedupe_key"],
        unique=False,
    )
    op.create_index(
        "ix_continuity_threads_owner_character_status",
        "continuity_threads",
        ["user_id", "character_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_continuity_threads_owner_character_status",
        table_name="continuity_threads",
    )
    op.drop_index("ix_continuity_threads_dedupe_key", table_name="continuity_threads")
    op.drop_index("ix_continuity_threads_status", table_name="continuity_threads")
    op.drop_index("ix_continuity_threads_source_message_id", table_name="continuity_threads")
    op.drop_index("ix_continuity_threads_conversation_id", table_name="continuity_threads")
    op.drop_index("ix_continuity_threads_character_id", table_name="continuity_threads")
    op.drop_index("ix_continuity_threads_user_id", table_name="continuity_threads")
    op.drop_table("continuity_threads")
