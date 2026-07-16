"""Add inspectable Living Memory lifecycle, evidence, and entities."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_living_memory"
down_revision = "0011_witnessed_continuity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column("retention_tier", sa.String(length=16), server_default="normal", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("lifecycle_state", sa.String(length=16), server_default="active", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("sensitivity", sa.String(length=16), server_default="standard", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column(
            "emotional_context_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "memory_items",
        sa.Column("novelty", sa.Float(), server_default="0.5", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("future_relevance", sa.Float(), server_default="0.5", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("reinforcement_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "memory_items",
        sa.Column("last_reinforced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "memory_items",
        sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "memory_items",
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_memory_items_superseded_by_id",
        "memory_items",
        "memory_items",
        ["superseded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE memory_items SET "
        "lifecycle_state = CASE WHEN forgotten_at IS NULL THEN 'active' ELSE 'forgotten' END, "
        "retention_tier = CASE "
        "WHEN pinned OR memory_type IN ('boundary', 'relationship_milestone') THEN 'core' "
        "WHEN memory_type IN ('event', 'theme') AND importance < 0.45 THEN 'transient' "
        "ELSE 'normal' END, "
        "last_reinforced_at = updated_at, last_evidence_at = updated_at"
    )
    op.create_check_constraint(
        "ck_memory_items_retention_tier",
        "memory_items",
        "retention_tier IN ('transient', 'normal', 'core')",
    )
    op.create_check_constraint(
        "ck_memory_items_lifecycle_state",
        "memory_items",
        "lifecycle_state IN ('active', 'superseded', 'forgotten')",
    )
    op.create_check_constraint(
        "ck_memory_items_sensitivity",
        "memory_items",
        "sensitivity IN ('standard', 'sensitive')",
    )
    op.create_check_constraint(
        "ck_memory_items_novelty",
        "memory_items",
        "novelty >= 0 AND novelty <= 1",
    )
    op.create_check_constraint(
        "ck_memory_items_future_relevance",
        "memory_items",
        "future_relevance >= 0 AND future_relevance <= 1",
    )
    op.create_check_constraint(
        "ck_memory_items_reinforcement_count",
        "memory_items",
        "reinforcement_count >= 1",
    )
    op.create_index(
        "ix_memory_items_retention_tier", "memory_items", ["retention_tier"], unique=False
    )
    op.create_index(
        "ix_memory_items_lifecycle_state", "memory_items", ["lifecycle_state"], unique=False
    )
    op.create_index("ix_memory_items_sensitivity", "memory_items", ["sensitivity"], unique=False)
    op.create_index(
        "ix_memory_items_superseded_by_id", "memory_items", ["superseded_by_id"], unique=False
    )
    op.create_index(
        "ix_memory_items_living_retrieval",
        "memory_items",
        ["user_id", "character_id", "scope", "lifecycle_state", "forgotten_at"],
        unique=False,
    )

    op.create_table(
        "memory_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("actor", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column(
            "snapshot_json",
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
        sa.CheckConstraint(
            "action IN ('created', 'reinforced', 'merged', 'edited', 'corrected', "
            "'forgotten', 'restored', 'resolved')",
            name="ck_memory_evidence_action",
        ),
        sa.CheckConstraint("actor IN ('system', 'user')", name="ck_memory_evidence_actor"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_evidence_memory_id", "memory_evidence", ["memory_id"], unique=False)
    op.create_index(
        "ix_memory_evidence_source_message_id",
        "memory_evidence",
        ["source_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_memory_evidence_created_at", "memory_evidence", ["created_at"], unique=False
    )

    op.create_table(
        "memory_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mention_count", sa.Integer(), server_default="1", nullable=False),
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
            "entity_type IN ('date', 'person', 'place', 'project', 'routine', 'topic')",
            name="ck_memory_entities_type",
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "character_id",
            "entity_type",
            "normalized_name",
            name="uq_memory_entities_owner_character_identity",
        ),
    )
    op.create_index("ix_memory_entities_user_id", "memory_entities", ["user_id"], unique=False)
    op.create_index(
        "ix_memory_entities_character_id", "memory_entities", ["character_id"], unique=False
    )
    op.create_index(
        "ix_memory_entities_entity_type", "memory_entities", ["entity_type"], unique=False
    )
    op.create_index(
        "ix_memory_entities_normalized_name",
        "memory_entities",
        ["normalized_name"],
        unique=False,
    )

    op.create_table(
        "memory_entity_links",
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation", sa.String(length=40), server_default="about", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["memory_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("memory_id", "entity_id"),
    )
    op.create_index(
        "ix_memory_entity_links_entity_id",
        "memory_entity_links",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_entity_links_entity_id", table_name="memory_entity_links")
    op.drop_table("memory_entity_links")
    op.drop_index("ix_memory_entities_normalized_name", table_name="memory_entities")
    op.drop_index("ix_memory_entities_entity_type", table_name="memory_entities")
    op.drop_index("ix_memory_entities_character_id", table_name="memory_entities")
    op.drop_index("ix_memory_entities_user_id", table_name="memory_entities")
    op.drop_table("memory_entities")
    op.drop_index("ix_memory_evidence_created_at", table_name="memory_evidence")
    op.drop_index("ix_memory_evidence_source_message_id", table_name="memory_evidence")
    op.drop_index("ix_memory_evidence_memory_id", table_name="memory_evidence")
    op.drop_table("memory_evidence")
    op.drop_index("ix_memory_items_living_retrieval", table_name="memory_items")
    op.drop_index("ix_memory_items_superseded_by_id", table_name="memory_items")
    op.drop_index("ix_memory_items_sensitivity", table_name="memory_items")
    op.drop_index("ix_memory_items_lifecycle_state", table_name="memory_items")
    op.drop_index("ix_memory_items_retention_tier", table_name="memory_items")
    op.drop_constraint("ck_memory_items_reinforcement_count", "memory_items", type_="check")
    op.drop_constraint("ck_memory_items_future_relevance", "memory_items", type_="check")
    op.drop_constraint("ck_memory_items_novelty", "memory_items", type_="check")
    op.drop_constraint("ck_memory_items_sensitivity", "memory_items", type_="check")
    op.drop_constraint("ck_memory_items_lifecycle_state", "memory_items", type_="check")
    op.drop_constraint("ck_memory_items_retention_tier", "memory_items", type_="check")
    op.drop_constraint("fk_memory_items_superseded_by_id", "memory_items", type_="foreignkey")
    op.drop_column("memory_items", "superseded_by_id")
    op.drop_column("memory_items", "last_evidence_at")
    op.drop_column("memory_items", "last_reinforced_at")
    op.drop_column("memory_items", "reinforcement_count")
    op.drop_column("memory_items", "future_relevance")
    op.drop_column("memory_items", "novelty")
    op.drop_column("memory_items", "emotional_context_json")
    op.drop_column("memory_items", "sensitivity")
    op.drop_column("memory_items", "lifecycle_state")
    op.drop_column("memory_items", "retention_tier")
