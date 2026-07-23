from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.companion.soul import canonical_soul_json
from app.db.session import get_session
from app.dependencies import get_current_user, require_character
from app.models import Character, EpisodicJournal, MemoryItem, RelationshipEvent, User
from app.schemas import (
    AdultGateStatus,
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    DeleteResponse,
    RelationshipEventOut,
    RelationshipEventUpdate,
    RelationshipOut,
    RelationshipResetRequest,
)
from app.services.proactive import proactive_preferences, reschedule_pending_proactive_jobs
from app.services.relationship import (
    active_relationship_boundaries,
    correct_relationship_event,
    delete_relationship_event,
    get_current_relationship,
    get_or_create_relationship,
    list_relationship_events,
    relationship_event_public_dict,
    reset_relationship,
)
from app.services.safety import (
    adult_gate_status,
    canonicalize_character_adult_settings,
    validate_character_adult_profile,
)

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterOut])
async def list_characters(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Character]:
    result = await session.execute(
        select(Character).where(Character.owner_user_id == user.id).order_by(Character.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=CharacterOut, status_code=201)
async def create_character(
    payload: CharacterCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    validate_character_adult_profile(
        name=payload.name,
        description=payload.description,
        personality_core=payload.personality_core,
        speech_style=payload.speech_style,
        boundaries_json={
            **payload.boundaries_json,
            "character_soul": payload.soul_json.model_dump(mode="json"),
        },
        explicit_age=payload.explicit_age,
        adult_mode_allowed=payload.adult_mode_allowed,
    )
    values = payload.model_dump()
    values["soul_json"] = canonical_soul_json(payload.soul_json)
    values["boundaries_json"], values["content_intensity"] = canonicalize_character_adult_settings(
        boundaries_json=payload.boundaries_json,
        adult_mode_allowed=payload.adult_mode_allowed,
        content_intensity=payload.content_intensity,
    )
    character = Character(owner_user_id=user.id, **values)
    session.add(character)
    await session.flush()
    await get_or_create_relationship(session, user.id, character.id)
    await session.commit()
    await session.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterOut)
async def get_character(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    return await require_character(character_id, user, session)


@router.patch("/{character_id}", response_model=CharacterOut)
async def update_character(
    character_id: uuid.UUID,
    payload: CharacterUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Character:
    character = await require_character(character_id, user, session)
    previous_proactive_preferences = dict(proactive_preferences(character))
    updates = payload.model_dump(exclude_unset=True)
    next_boundaries = updates.get("boundaries_json", character.boundaries_json)
    next_soul = updates.get("soul_json", character.soul_json)
    next_adult_mode_allowed = updates.get("adult_mode_allowed", character.adult_mode_allowed)
    next_content_intensity = updates.get("content_intensity", character.content_intensity)
    validate_character_adult_profile(
        name=updates.get("name", character.name),
        description=updates.get("description", character.description),
        personality_core=updates.get("personality_core", character.personality_core),
        speech_style=updates.get("speech_style", character.speech_style),
        boundaries_json={**next_boundaries, "character_soul": next_soul},
        explicit_age=updates.get("explicit_age", character.explicit_age),
        adult_mode_allowed=next_adult_mode_allowed,
    )
    updates["boundaries_json"], updates["content_intensity"] = (
        canonicalize_character_adult_settings(
            boundaries_json=next_boundaries,
            adult_mode_allowed=next_adult_mode_allowed,
            content_intensity=next_content_intensity,
        )
    )
    updates["soul_json"] = canonical_soul_json(next_soul, character=character)
    for field, value in updates.items():
        setattr(character, field, value)
    if (
        "boundaries_json" in updates
        and proactive_preferences(character) != previous_proactive_preferences
    ):
        await reschedule_pending_proactive_jobs(session, character)
    await session.commit()
    await session.refresh(character)
    return character


@router.get("/{character_id}/relationship", response_model=RelationshipOut)
async def get_relationship(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    character = await require_character(character_id, user, session)
    relationship = await get_current_relationship(session, user.id, character.id)
    await session.commit()
    await session.refresh(relationship)
    return relationship


@router.get(
    "/{character_id}/relationship/events",
    response_model=list[RelationshipEventOut],
)
async def get_relationship_events(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    scope: Literal["general", "adult"] = "general",
) -> list[dict[str, object]]:
    character = await require_character(character_id, user, session)
    events = await list_relationship_events(
        session,
        user_id=user.id,
        character_id=character.id,
        scopes=(scope,),
    )
    active_boundaries = await active_relationship_boundaries(
        session,
        user_id=user.id,
        character_id=character.id,
        scopes=(scope,),
    )
    active_ids = {event.id for event in active_boundaries}
    return [
        relationship_event_public_dict(event, active_boundary_ids=active_ids) for event in events
    ]


@router.patch(
    "/{character_id}/relationship/events/{event_id}",
    response_model=RelationshipEventOut,
)
async def update_relationship_event(
    character_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: RelationshipEventUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    character = await require_character(character_id, user, session)
    event = await _owned_relationship_event(
        session,
        user_id=user.id,
        character_id=character.id,
        event_id=event_id,
    )
    relationship = await get_current_relationship(session, user.id, character.id)
    try:
        event = await correct_relationship_event(
            session,
            event=event,
            state=relationship,
            summary=payload.summary,
            event_type=payload.event_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    await session.refresh(event)
    active = await active_relationship_boundaries(
        session,
        user_id=user.id,
        character_id=character.id,
        scopes=(event.scope,),
    )
    return relationship_event_public_dict(
        event,
        active_boundary_ids={item.id for item in active},
    )


@router.delete(
    "/{character_id}/relationship/events/{event_id}",
    response_model=DeleteResponse,
)
async def remove_relationship_event(
    character_id: uuid.UUID,
    event_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    event = await _owned_relationship_event(
        session,
        user_id=user.id,
        character_id=character.id,
        event_id=event_id,
    )
    relationship = await get_current_relationship(session, user.id, character.id)
    await delete_relationship_event(session, event=event, state=relationship)
    await session.commit()
    return DeleteResponse(deleted=1)


@router.post(
    "/{character_id}/relationship/reset",
    response_model=RelationshipOut,
)
async def reset_relationship_state(
    character_id: uuid.UUID,
    payload: RelationshipResetRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    character = await require_character(character_id, user, session)
    relationship = await get_current_relationship(session, user.id, character.id)
    relationship = await reset_relationship(
        session,
        state=relationship,
        mode=payload.mode,
        dimensions=tuple(dict.fromkeys(payload.dimensions or ())) or None,
    )
    await session.commit()
    await session.refresh(relationship)
    return relationship


@router.get("/{character_id}/adult-status", response_model=AdultGateStatus)
async def get_adult_status(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    character = await require_character(character_id, user, session)
    relationship = await get_current_relationship(session, user.id, character.id)
    status = adult_gate_status(user, character, "adult", relationship=relationship)
    memory_count = await session.scalar(
        select(func.count(MemoryItem.id)).where(
            MemoryItem.user_id == user.id,
            MemoryItem.character_id == character.id,
            MemoryItem.scope == "adult",
        )
    )
    moment_count = await session.scalar(
        select(func.count(EpisodicJournal.id)).where(
            EpisodicJournal.user_id == user.id,
            EpisodicJournal.character_id == character.id,
            EpisodicJournal.scope == "adult",
        )
    )
    status["stored_memory_count"] = int(memory_count or 0)
    status["stored_moment_count"] = int(moment_count or 0)
    await session.commit()
    return status


@router.delete("/{character_id}/adult-continuity", response_model=DeleteResponse)
async def delete_adult_continuity(
    character_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeleteResponse:
    character = await require_character(character_id, user, session)
    memory_result = await session.execute(
        delete(MemoryItem).where(
            MemoryItem.user_id == user.id,
            MemoryItem.character_id == character.id,
            MemoryItem.scope == "adult",
        )
    )
    moment_result = await session.execute(
        delete(EpisodicJournal).where(
            EpisodicJournal.user_id == user.id,
            EpisodicJournal.character_id == character.id,
            EpisodicJournal.scope == "adult",
        )
    )
    relationship_result = await session.execute(
        delete(RelationshipEvent).where(
            RelationshipEvent.user_id == user.id,
            RelationshipEvent.character_id == character.id,
            RelationshipEvent.scope == "adult",
        )
    )
    await session.commit()
    return DeleteResponse(
        deleted=(
            int(memory_result.rowcount or 0)
            + int(moment_result.rowcount or 0)
            + int(relationship_result.rowcount or 0)
        )
    )


async def _owned_relationship_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    character_id: uuid.UUID,
    event_id: uuid.UUID,
) -> RelationshipEvent:
    result = await session.execute(
        select(RelationshipEvent).where(
            RelationshipEvent.id == event_id,
            RelationshipEvent.user_id == user_id,
            RelationshipEvent.character_id == character_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Relationship moment not found.")
    return event
