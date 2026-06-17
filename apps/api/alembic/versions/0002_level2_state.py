"""Add Level 2 memory, journal, and relationship state."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_level2_state"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "memory_items",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "memory_items",
        sa.Column("contradiction_group", sa.String(length=120), nullable=True),
    )

    op.add_column(
        "relationship_states",
        sa.Column("mood", sa.String(length=80), nullable=False, server_default="steady"),
    )
    op.add_column(
        "relationship_states",
        sa.Column("conflict_state", sa.String(length=80), nullable=False, server_default="clear"),
    )
    op.add_column(
        "relationship_states",
        sa.Column("repair_needed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "relationship_states",
        sa.Column(
            "tags_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_table(
        "episodic_journals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("emotional_tags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "unresolved_threads_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("callbacks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_episodic_journals_user_id", "episodic_journals", ["user_id"])
    op.create_index(
        "ix_episodic_journals_character_id",
        "episodic_journals",
        ["character_id"],
    )
    op.create_index(
        "ix_episodic_journals_conversation_id",
        "episodic_journals",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_episodic_journals_conversation_id", table_name="episodic_journals")
    op.drop_index("ix_episodic_journals_character_id", table_name="episodic_journals")
    op.drop_index("ix_episodic_journals_user_id", table_name="episodic_journals")
    op.drop_table("episodic_journals")

    op.drop_column("relationship_states", "tags_json")
    op.drop_column("relationship_states", "repair_needed")
    op.drop_column("relationship_states", "conflict_state")
    op.drop_column("relationship_states", "mood")

    op.drop_column("memory_items", "contradiction_group")
    op.drop_column("memory_items", "pinned")
    op.drop_column("memory_items", "importance")
