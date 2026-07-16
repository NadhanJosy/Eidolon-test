"""Add scoped, source-grounded continuity state."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_witnessed_continuity"
down_revision = "0010_living_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column("scope", sa.String(length=16), server_default="general", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("claim_key", sa.String(length=160), nullable=True),
    )
    op.create_check_constraint(
        "ck_memory_items_scope",
        "memory_items",
        "scope IN ('general', 'adult')",
    )
    op.create_index("ix_memory_items_scope", "memory_items", ["scope"], unique=False)
    op.create_index("ix_memory_items_claim_key", "memory_items", ["claim_key"], unique=False)
    op.create_index(
        "ix_memory_items_owner_character_scope",
        "memory_items",
        ["user_id", "character_id", "scope"],
        unique=False,
    )

    op.add_column(
        "episodic_journals",
        sa.Column("scope", sa.String(length=16), server_default="general", nullable=False),
    )
    op.create_check_constraint(
        "ck_episodic_journals_scope",
        "episodic_journals",
        "scope IN ('general', 'adult')",
    )
    op.create_index(
        "ix_episodic_journals_scope",
        "episodic_journals",
        ["scope"],
        unique=False,
    )
    op.create_index(
        "ix_episodic_journals_owner_character_scope",
        "episodic_journals",
        ["user_id", "character_id", "scope"],
        unique=False,
    )

    op.create_table(
        "episodic_journal_sources",
        sa.Column("journal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["episodic_journals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("journal_id", "message_id"),
    )
    op.create_index(
        "ix_episodic_journal_sources_message_id",
        "episodic_journal_sources",
        ["message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_episodic_journal_sources_message_id",
        table_name="episodic_journal_sources",
    )
    op.drop_table("episodic_journal_sources")
    op.drop_index(
        "ix_episodic_journals_owner_character_scope",
        table_name="episodic_journals",
    )
    op.drop_index("ix_episodic_journals_scope", table_name="episodic_journals")
    op.drop_constraint(
        "ck_episodic_journals_scope",
        "episodic_journals",
        type_="check",
    )
    op.drop_column("episodic_journals", "scope")
    op.drop_index("ix_memory_items_owner_character_scope", table_name="memory_items")
    op.drop_index("ix_memory_items_claim_key", table_name="memory_items")
    op.drop_index("ix_memory_items_scope", table_name="memory_items")
    op.drop_constraint("ck_memory_items_scope", "memory_items", type_="check")
    op.drop_column("memory_items", "claim_key")
    op.drop_column("memory_items", "scope")
