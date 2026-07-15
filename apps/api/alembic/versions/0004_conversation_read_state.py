"""Add a durable read cursor to conversations."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_conversation_read_state"
down_revision = "0003_conversation_privacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "last_read_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "last_read_at")
