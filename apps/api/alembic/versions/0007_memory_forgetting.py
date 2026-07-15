"""Add reversible forgotten state to memories."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_memory_forgetting"
down_revision = "0006_auth_throttles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column("forgotten_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_memory_items_forgotten_at"),
        "memory_items",
        ["forgotten_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_items_forgotten_at"), table_name="memory_items")
    op.drop_column("memory_items", "forgotten_at")
