"""Generalize login throttles to auth throttles."""

from __future__ import annotations

from alembic import op

revision = "0006_auth_throttles"
down_revision = "0005_login_throttles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_login_throttles_last_attempt_at"),
        table_name="login_throttles",
    )
    op.rename_table("login_throttles", "auth_throttles")
    op.execute(
        "ALTER TABLE auth_throttles RENAME CONSTRAINT login_throttles_pkey TO auth_throttles_pkey"
    )
    op.execute(
        "ALTER TABLE auth_throttles "
        "RENAME CONSTRAINT ck_login_throttles_failed_attempts "
        "TO ck_auth_throttles_failed_attempts"
    )
    op.create_index(
        op.f("ix_auth_throttles_last_attempt_at"),
        "auth_throttles",
        ["last_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_auth_throttles_last_attempt_at"),
        table_name="auth_throttles",
    )
    op.execute(
        "ALTER TABLE auth_throttles RENAME CONSTRAINT auth_throttles_pkey TO login_throttles_pkey"
    )
    op.execute(
        "ALTER TABLE auth_throttles "
        "RENAME CONSTRAINT ck_auth_throttles_failed_attempts "
        "TO ck_login_throttles_failed_attempts"
    )
    op.rename_table("auth_throttles", "login_throttles")
    op.create_index(
        op.f("ix_login_throttles_last_attempt_at"),
        "login_throttles",
        ["last_attempt_at"],
        unique=False,
    )
