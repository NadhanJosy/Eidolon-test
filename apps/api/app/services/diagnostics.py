from __future__ import annotations

import logging
import uuid
from typing import Literal

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models import DiagnosticEvent

logger = logging.getLogger(__name__)

MAX_DIAGNOSTIC_EVENTS_PER_USER = 100

DiagnosticCode = Literal[
    "authentication",
    "context_overflow",
    "generation_failed",
    "malformed_response",
    "model_unavailable",
    "provider_unavailable",
    "quota_exhausted",
    "rate_limited",
    "refusal",
    "timeout",
]
DiagnosticOperation = Literal["message", "stream", "reroll", "edit"]

SAFE_MESSAGES: dict[DiagnosticCode, str] = {
    "provider_unavailable": "The configured text provider was unavailable.",
    "generation_failed": "Reply generation ended unexpectedly.",
    "authentication": "The configured text provider rejected its credentials.",
    "context_overflow": "The provider context limit was reached.",
    "malformed_response": "The provider returned an unreadable response.",
    "model_unavailable": "The configured text model was unavailable.",
    "quota_exhausted": "The configured provider quota was exhausted.",
    "rate_limited": "The configured provider rate limit was reached.",
    "refusal": "The configured provider declined the response.",
    "timeout": "The configured text provider timed out.",
}


async def record_generation_error(
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    conversation_id: uuid.UUID,
    operation: DiagnosticOperation,
    code: DiagnosticCode,
    provider: str,
) -> None:
    """Persist a bounded safe event without changing the original request outcome."""
    try:
        async with AsyncSessionLocal() as session:
            event = DiagnosticEvent(
                user_id=user_id,
                character_id=character_id,
                conversation_id=conversation_id,
                source="chat",
                operation=operation,
                code=code,
                provider=_safe_provider_label(provider),
                safe_message=SAFE_MESSAGES[code],
            )
            session.add(event)
            await session.flush()
            retained_ids = (
                select(DiagnosticEvent.id)
                .where(DiagnosticEvent.user_id == user_id)
                .order_by(DiagnosticEvent.created_at.desc(), DiagnosticEvent.id.desc())
                .limit(MAX_DIAGNOSTIC_EVENTS_PER_USER)
            )
            await session.execute(
                delete(DiagnosticEvent).where(
                    DiagnosticEvent.user_id == user_id,
                    DiagnosticEvent.id.not_in(retained_ids),
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - diagnostics must never replace the primary failure
        logger.exception("Could not persist a safe diagnostic event.")


def _safe_provider_label(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in {"groq", "mock", "ollama"} else "unknown"
