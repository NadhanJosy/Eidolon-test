"""Add unified proactive candidates and durable delivery metadata.

Revision ID: 0014_proactive_presence
Revises: 0013_relationship_intelligence
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014_proactive_presence"
down_revision = "0013_relationship_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scheduled_jobs", sa.Column("dedupe_key", sa.String(180), nullable=True))
    op.add_column(
        "scheduled_jobs",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_scheduled_jobs_dedupe_key",
        "scheduled_jobs",
        ["dedupe_key"],
    )
    op.create_index(
        "ix_scheduled_jobs_expires_at",
        "scheduled_jobs",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "proactive_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("continuity_thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relationship_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_type", sa.String(32), nullable=False),
        sa.Column("initiative_kind", sa.String(16), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("rationale", sa.String(240), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("urgency", sa.Float(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("sensitivity", sa.String(16), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notification_preview", sa.String(180), nullable=False),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("dismissal_feedback", sa.String(32), nullable=True),
        sa.Column(
            "delivery_constraints_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "score_factors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_type IN ('follow_up', 'check_in', 'reminder', 'callback', "
            "'milestone', 'routine', 'return', 'suggestion', 'queued_thought')",
            name="ck_proactive_candidates_type",
        ),
        sa.CheckConstraint(
            "initiative_kind IN ('companion', 'reminder')",
            name="ck_proactive_candidates_initiative",
        ),
        sa.CheckConstraint(
            "state IN ('candidate', 'scheduled', 'generated', 'delivered', 'opened', "
            "'dismissed', 'replied', 'cancelled', 'failed', 'expired')",
            name="ck_proactive_candidates_state",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('standard', 'sensitive', 'adult', 'private')",
            name="ck_proactive_candidates_sensitivity",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_proactive_candidates_confidence",
        ),
        sa.CheckConstraint(
            "urgency >= 0 AND urgency <= 1",
            name="ck_proactive_candidates_urgency",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_proactive_candidates_relevance",
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["continuity_thread_id"],
            ["continuity_threads.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["journal_id"], ["episodic_journals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["relationship_event_id"],
            ["relationship_events.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_proactive_candidates_owner_idempotency",
        ),
        sa.UniqueConstraint("message_id", name="uq_proactive_candidates_message"),
    )
    for column in (
        "candidate_type",
        "character_id",
        "continuity_thread_id",
        "conversation_id",
        "expires_at",
        "journal_id",
        "memory_id",
        "relationship_event_id",
        "scheduled_for",
        "source_message_id",
        "state",
        "user_id",
    ):
        op.create_index(
            f"ix_proactive_candidates_{column}",
            "proactive_candidates",
            [column],
            unique=False,
        )

    op.create_table(
        "proactive_candidate_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.String(24), nullable=True),
        sa.Column("to_state", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "to_state IN ('candidate', 'scheduled', 'generated', 'delivered', 'opened', "
            "'dismissed', 'replied', 'cancelled', 'failed', 'expired')",
            name="ck_proactive_candidate_events_state",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["proactive_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proactive_candidate_events_candidate_id",
        "proactive_candidate_events",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_proactive_candidate_events_created_at",
        "proactive_candidate_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_proactive_candidate_events_to_state",
        "proactive_candidate_events",
        ["to_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_proactive_candidate_events_to_state",
        table_name="proactive_candidate_events",
    )
    op.drop_index(
        "ix_proactive_candidate_events_created_at",
        table_name="proactive_candidate_events",
    )
    op.drop_index(
        "ix_proactive_candidate_events_candidate_id",
        table_name="proactive_candidate_events",
    )
    op.drop_table("proactive_candidate_events")
    for column in (
        "user_id",
        "state",
        "source_message_id",
        "scheduled_for",
        "relationship_event_id",
        "memory_id",
        "journal_id",
        "expires_at",
        "conversation_id",
        "continuity_thread_id",
        "character_id",
        "candidate_type",
    ):
        op.drop_index(
            f"ix_proactive_candidates_{column}",
            table_name="proactive_candidates",
        )
    op.drop_table("proactive_candidates")
    op.drop_index("ix_scheduled_jobs_expires_at", table_name="scheduled_jobs")
    op.drop_constraint(
        "uq_scheduled_jobs_dedupe_key",
        "scheduled_jobs",
        type_="unique",
    )
    op.drop_column("scheduled_jobs", "cancelled_at")
    op.drop_column("scheduled_jobs", "expires_at")
    op.drop_column("scheduled_jobs", "dedupe_key")
