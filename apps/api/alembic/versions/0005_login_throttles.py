"""Add privacy-preserving login throttles."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_login_throttles"
down_revision = "0004_conversation_read_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "failed_attempts >= 1",
            name="ck_login_throttles_failed_attempts",
        ),
        sa.PrimaryKeyConstraint("fingerprint"),
    )
    op.create_index(
        op.f("ix_login_throttles_last_attempt_at"),
        "login_throttles",
        ["last_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_login_throttles_last_attempt_at"),
        table_name="login_throttles",
    )
    op.drop_table("login_throttles")
