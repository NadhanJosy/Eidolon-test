"""Add evidence-backed relationship intelligence and user controls."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_relationship_intelligence"
down_revision = "0012_living_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, default in (
        ("emotional_safety", "50"),
        ("reliability", "50"),
        ("reciprocity", "0"),
        ("repair_progress", "0"),
        ("boundary_alignment", "100"),
        ("shared_history_depth", "0"),
    ):
        op.add_column(
            "relationship_states",
            sa.Column(name, sa.Float(), server_default=default, nullable=False),
        )
        op.create_check_constraint(
            f"ck_relationship_states_{name}",
            "relationship_states",
            f"{name} >= 0 AND {name} <= 100",
        )

    op.create_table(
        "relationship_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=16), server_default="general", nullable=False),
        sa.Column("event_key", sa.String(length=96), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("evidence_quote", sa.String(length=600), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("significance", sa.Float(), nullable=False),
        sa.Column(
            "dimension_deltas_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "affects_current_state",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
            "scope IN ('general', 'adult')",
            name="ck_relationship_events_scope",
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'support', 'vulnerability', 'promise', 'consistency', 'promise_broken', "
            "'conflict', 'apology', 'boundary_set', 'boundary_violation', "
            "'boundary_revoked', 'repair', 'humor', 'ritual', 'milestone', "
            "'absence', 'return', 'reset')",
            name="ck_relationship_events_type",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_relationship_events_confidence",
        ),
        sa.CheckConstraint(
            "significance >= 0 AND significance <= 1",
            name="ck_relationship_events_significance",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["episodic_journals.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "character_id",
            "event_key",
            name="uq_relationship_events_owner_character_key",
        ),
    )
    for column in (
        "user_id",
        "character_id",
        "source_message_id",
        "memory_id",
        "journal_id",
        "scope",
        "event_type",
        "occurred_at",
    ):
        op.create_index(
            f"ix_relationship_events_{column}",
            "relationship_events",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_relationship_events_owner_character_scope_time",
        "relationship_events",
        ["user_id", "character_id", "scope", "occurred_at"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO relationship_events (
            id, user_id, character_id, scope, event_key, event_type, summary,
            confidence, significance, dimension_deltas_json, affects_current_state,
            occurred_at, metadata_json, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), user_id, character_id, 'general',
            'legacy-snapshot:' || id::text, 'reset',
            'Earlier relationship history was carried forward.',
            1.0, 0.0, '{}'::jsonb, false,
            COALESCE(last_interaction_at, updated_at),
            jsonb_build_object(
                'origin', 'migration',
                'preserves_legacy_state', true
            ),
            now(), now()
        FROM relationship_states
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_relationship_events_owner_character_scope_time",
        table_name="relationship_events",
    )
    for column in (
        "occurred_at",
        "event_type",
        "scope",
        "journal_id",
        "memory_id",
        "source_message_id",
        "character_id",
        "user_id",
    ):
        op.drop_index(f"ix_relationship_events_{column}", table_name="relationship_events")
    op.drop_table("relationship_events")
    for name in (
        "shared_history_depth",
        "boundary_alignment",
        "repair_progress",
        "reciprocity",
        "reliability",
        "emotional_safety",
    ):
        op.drop_constraint(
            f"ck_relationship_states_{name}",
            "relationship_states",
            type_="check",
        )
        op.drop_column("relationship_states", name)
