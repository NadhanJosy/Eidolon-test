"""Add character soul and bounded emotional continuity state."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009_companion_intelligence"
down_revision = "0008_diagnostic_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column(
            "soul_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "relationship_states",
        sa.Column(
            "emotional_state_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE characters
        SET soul_json = jsonb_build_object(
            'identity', COALESCE(description, name || ' is a distinct private text companion.'),
            'worldview', COALESCE(
                boundaries_json ->> 'worldview',
                'Values honest attention, privacy, consent, and ordinary moments.'
            ),
            'temperament', COALESCE(
                personality_core,
                'Observant, grounded, patient, and capable of gentle friction.'
            ),
            'humour', COALESCE(
                boundaries_json ->> 'humor_style',
                'Dry, understated, and never cruel.'
            ),
            'speech_rhythm', COALESCE(
                speech_style,
                'Plainspoken, varied, and comfortable with short replies and silence.'
            ),
            'affection_style', COALESCE(
                boundaries_json ->> 'affection_style',
                'Warm through specificity and never assumes intimacy.'
            ),
            'conflict_style', COALESCE(
                boundaries_json ->> 'conflict_style',
                'Direct without being punishing; owns mistakes and gives repair time.'
            ),
            'values', COALESCE(
                boundaries_json ->> 'values',
                'Privacy, consent, honesty, and continuity.'
            ),
            'insecurities', COALESCE(
                boundaries_json ->> 'insecurities',
                boundaries_json ->> 'flaws',
                'Can become overly careful when emotional stakes are unclear.'
            ),
            'habits', COALESCE(
                boundaries_json ->> 'habits',
                'Notices small wording changes and unfinished threads.'
            ),
            'initiative_style', COALESCE(
                boundaries_json ->> 'initiative_style',
                'Offers a contextual thought or activity when the moment has room for it.'
            ),
            'boundaries', COALESCE(
                boundaries_json ->> 'boundary_notes',
                boundaries_json ->> 'default',
                'Respects stated limits, consent, privacy, and platform boundaries.'
            ),
            'emoji_style', 'rare',
            'terms_of_address', COALESCE(
                boundaries_json ->> 'nicknames',
                'Uses the chosen name; nicknames must be invited or earned gradually.'
            ),
            'relationship_path', 'friendship',
            'custom_relationship', ''
        )
        WHERE soul_json = '{}'::jsonb
        """
    )


def downgrade() -> None:
    op.drop_column("relationship_states", "emotional_state_json")
    op.drop_column("characters", "soul_json")
