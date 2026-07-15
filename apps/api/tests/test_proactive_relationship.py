from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from helpers import auth_headers
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.llm.base import LLMGeneration, LLMProviderUnavailable
from app.models import Conversation, Message, RelationshipState, ScheduledJob, utc_now
from app.services.jobs import create_job
from app.services.proactive import (
    DELAYED_DOUBLE_TEXT_TYPE,
    create_inactivity_proactive_message,
    ensure_proactive_jobs,
    proactive_relationship_posture,
)
from app.services.scheduler import process_due_jobs


class RecordingProactiveProvider:
    name = "recording-test"
    model = "recording-test"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMGeneration:
        self.prompts.append(prompt)
        return LLMGeneration(
            "A gentle hello, with no pressure to answer before it feels right.",
            self.name,
            self.model,
        )


class UnavailableProactiveProvider:
    name = "offline-test"
    model = "offline-test"

    async def generate(self, prompt: str) -> str:
        raise LLMProviderUnavailable("Local model is unavailable in this test.")


@pytest.mark.parametrize(
    ("state", "expected_key"),
    [
        (None, "new"),
        (
            RelationshipState(
                trust=float("-inf"),
                warmth=float("nan"),
                tension=float("inf"),
            ),
            "new",
        ),
        (RelationshipState(familiarity=8.0), "warming"),
        (RelationshipState(trust=10.0, warmth=8.0), "trusted"),
        (RelationshipState(intimacy=20.0), "close"),
        (RelationshipState(tension=5.0, conflict_state="watchful"), "careful"),
        (RelationshipState(repair_needed=True, conflict_state="strained"), "repair"),
    ],
)
def test_proactive_relationship_posture_is_qualitative_and_bounded(
    state: RelationshipState | None,
    expected_key: str,
) -> None:
    posture = proactive_relationship_posture(state)

    assert posture.key == expected_key
    assert posture.guidance
    assert len(posture.guidance) <= 160
    assert "/100" not in posture.guidance
    assert not any(character.isdigit() for character in posture.guidance)


async def test_proactive_prompt_uses_qualitative_relationship_posture_only(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_data = (await client.post("/conversations", json={}, headers=headers)).json()
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_data["id"], "content": "A quiet hello."},
        headers=headers,
    )
    assert chat.status_code == 200

    provider = RecordingProactiveProvider()
    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, uuid.UUID(conversation_data["id"]))
        assert conversation is not None
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.user_id == conversation.user_id,
                    RelationshipState.character_id == conversation.character_id,
                )
            )
        ).scalar_one()
        relationship.trust = 10.0
        relationship.warmth = 8.0
        relationship.familiarity = 12.0
        relationship.tension = 0.0
        relationship.conflict_state = "clear"
        relationship.repair_needed = False
        message = await create_inactivity_proactive_message(
            session,
            conversation,
            inactivity_hours=1,
            force=True,
            proactive_type="proactive_thinking_of_you",
            provider=provider,
        )
        await session.commit()

    assert message is not None
    assert message.metadata_json["relationship_posture"] == "trusted"
    assert len(provider.prompts) == 1
    prompt = provider.prompts[0]
    assert "Relational posture: trusted and warm" in prompt
    assert "Relationship state:" not in prompt
    assert "/100" not in prompt
    assert "trust 10" not in prompt.lower()
    assert "warmth 8" not in prompt.lower()


async def test_repair_posture_suppresses_pressure_and_uses_spacious_fallback(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_data = (await client.post("/conversations", json={}, headers=headers)).json()
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_data["id"], "content": "I need some room today."},
        headers=headers,
    )
    assert chat.status_code == 200

    recording_provider = RecordingProactiveProvider()
    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, uuid.UUID(conversation_data["id"]))
        assert conversation is not None
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.user_id == conversation.user_id,
                    RelationshipState.character_id == conversation.character_id,
                )
            )
        ).scalar_one()
        relationship.tension = 20.0
        relationship.conflict_state = "strained"
        relationship.repair_needed = True
        await session.execute(
            delete(ScheduledJob).where(ScheduledJob.character_id == conversation.character_id)
        )
        created_jobs = await ensure_proactive_jobs(
            session,
            conversation=conversation,
            user_id=conversation.user_id,
            character_id=conversation.character_id,
        )
        assert DELAYED_DOUBLE_TEXT_TYPE not in {job.job_type for job in created_jobs}

        suppressed = await create_inactivity_proactive_message(
            session,
            conversation,
            inactivity_hours=1,
            force=True,
            proactive_type=DELAYED_DOUBLE_TEXT_TYPE,
            provider=recording_provider,
        )
        assert suppressed is None
        assert recording_provider.prompts == []

        fallback = await create_inactivity_proactive_message(
            session,
            conversation,
            inactivity_hours=1,
            force=True,
            proactive_type="proactive_thinking_of_you",
            provider=UnavailableProactiveProvider(),
        )
        await session.commit()

    assert fallback is not None
    assert fallback.metadata_json["relationship_posture"] == "repair"
    assert fallback.metadata_json["generation_source"] == "fallback"
    assert fallback.metadata_json["generation_reason"] == "provider_unavailable"
    assert "nothing you need to settle" in fallback.content.lower()
    assert "no reply is expected" in fallback.content.lower()


async def test_scheduler_records_relationship_suppression_without_writing_note(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_data = (await client.post("/conversations", json={}, headers=headers)).json()
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_data["id"], "content": "I need a pause."},
        headers=headers,
    )
    assert chat.status_code == 200

    conversation_id = uuid.UUID(conversation_data["id"])
    async with AsyncSessionLocal() as session:
        conversation = await session.get(Conversation, conversation_id)
        assert conversation is not None
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.user_id == conversation.user_id,
                    RelationshipState.character_id == conversation.character_id,
                )
            )
        ).scalar_one()
        relationship.repair_needed = True
        relationship.conflict_state = "strained"
        await session.execute(
            delete(ScheduledJob).where(ScheduledJob.character_id == conversation.character_id)
        )
        job = await create_job(
            session,
            job_type=DELAYED_DOUBLE_TEXT_TYPE,
            run_at=utc_now() - timedelta(minutes=1),
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            payload_json={
                "conversation_id": str(conversation.id),
                "proactive_type": DELAYED_DOUBLE_TEXT_TYPE,
                "source": "relationship-suppression-test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="relationship-guard-worker")
        await session.commit()
    assert processed == 1

    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_by_relationship_state"
        assert stored_job.payload_json["skip_reason"] == "relationship_repair"
        assert stored_job.payload_json["relationship_posture"] == "repair"
        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert proactive_messages.scalar_one_or_none() is None
