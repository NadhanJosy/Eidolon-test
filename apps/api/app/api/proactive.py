from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models import Character, Message, ProactiveCandidate, User
from app.schemas import ProactiveCandidateOut, ProactiveDismissRequest
from app.services.proactive import proactive_preferences
from app.services.proactive_presence import (
    ALL_STATES,
    PENDING_STATES,
    cancel_candidate,
    cancel_candidate_delivery_jobs,
    cancel_pending_for_character,
    mark_candidate_dismissed,
    mark_candidate_opened,
    public_candidate,
)

router = APIRouter(prefix="/proactive", tags=["proactive"])


@router.get("", response_model=list[ProactiveCandidateOut])
async def list_proactive_inbox(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    view: Literal["inbox", "history", "pending"] = "inbox",
    character_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    states = {
        "inbox": ("delivered", "opened", "replied"),
        "history": ALL_STATES,
        "pending": PENDING_STATES,
    }[view]
    statement = (
        select(ProactiveCandidate, Message)
        .outerjoin(Message, Message.id == ProactiveCandidate.message_id)
        .where(
            ProactiveCandidate.user_id == user.id,
            ProactiveCandidate.state.in_(states),
        )
    )
    if view == "inbox":
        statement = statement.where(ProactiveCandidate.message_id.is_not(None))
    if character_id is not None:
        statement = statement.where(ProactiveCandidate.character_id == character_id)
    rows = (
        await session.execute(
            statement.order_by(
                desc(ProactiveCandidate.delivered_at),
                desc(ProactiveCandidate.created_at),
            ).limit(limit)
        )
    ).all()
    return [public_candidate(candidate, include_message=message) for candidate, message in rows]


@router.post("/{candidate_id}/open", response_model=ProactiveCandidateOut)
async def open_proactive_item(
    candidate_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    candidate = await _owned_candidate(session, user.id, candidate_id, for_update=True)
    await mark_candidate_opened(session, candidate)
    message = await session.get(Message, candidate.message_id) if candidate.message_id else None
    await session.commit()
    return public_candidate(candidate, include_message=message)


@router.post("/{candidate_id}/dismiss", response_model=ProactiveCandidateOut)
async def dismiss_proactive_item(
    candidate_id: uuid.UUID,
    payload: ProactiveDismissRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    candidate = await _owned_candidate(session, user.id, candidate_id, for_update=True)
    await mark_candidate_dismissed(session, candidate, feedback=payload.feedback)
    if payload.feedback == "mute_similar":
        character = await session.get(Character, candidate.character_id)
        if character is None or character.owner_user_id != user.id:
            raise HTTPException(status_code=404, detail="Companion was not found.")
        preferences = dict(proactive_preferences(character))
        muted = {item for item in preferences.get("muted_categories", []) if isinstance(item, str)}
        muted.add(candidate.candidate_type)
        profile = (
            dict(character.boundaries_json) if isinstance(character.boundaries_json, dict) else {}
        )
        character.boundaries_json = {
            **profile,
            "proactive_preferences": {
                **preferences,
                "muted_categories": sorted(muted),
            },
        }
        await cancel_pending_for_character(
            session,
            character_id=character.id,
            reason_code="category_muted_by_feedback",
            candidate_type=candidate.candidate_type,
        )
    message = await session.get(Message, candidate.message_id) if candidate.message_id else None
    await session.commit()
    return public_candidate(candidate, include_message=message)


@router.post("/{candidate_id}/cancel", response_model=ProactiveCandidateOut)
async def cancel_proactive_item(
    candidate_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    candidate = await _owned_candidate(session, user.id, candidate_id, for_update=True)
    if candidate.state in PENDING_STATES:
        await cancel_candidate(session, candidate, "cancelled_by_user")
        await cancel_candidate_delivery_jobs(
            session,
            candidate,
            reason_code="cancelled_by_user",
        )
    message = await session.get(Message, candidate.message_id) if candidate.message_id else None
    await session.commit()
    return public_candidate(candidate, include_message=message)


async def _owned_candidate(
    session: AsyncSession,
    user_id: uuid.UUID,
    candidate_id: uuid.UUID,
    *,
    for_update: bool,
) -> ProactiveCandidate:
    statement = select(ProactiveCandidate).where(
        ProactiveCandidate.id == candidate_id,
        ProactiveCandidate.user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update()
    candidate = (await session.execute(statement)).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Companion note was not found.")
    return candidate
