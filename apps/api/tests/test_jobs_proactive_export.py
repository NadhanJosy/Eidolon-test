from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from helpers import auth_headers, register_user
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import func, select

from app.config import Settings
from app.db.session import AsyncSessionLocal
from app.llm.base import LLMGeneration, LLMProviderUnavailable
from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    MemoryItem,
    Message,
    ProactiveCandidate,
    RelationshipState,
    ScheduledJob,
    User,
    utc_now,
)
from app.services import scheduler as scheduler_service
from app.services.auth_session import REFRESH_COOKIE_NAME
from app.services.continuity import select_proactive_thread
from app.services.jobs import claim_due_jobs, create_job, mark_job_done
from app.services.journal import create_journal
from app.services.proactive import (
    proactive_deferred_until,
    proactive_initial_run_at,
)
from app.services.scheduler import process_due_jobs


async def test_job_claim_and_done() -> None:
    async with AsyncSessionLocal() as session:
        await create_job(
            session,
            job_type="maintenance_noop",
            run_at=utc_now() - timedelta(minutes=1),
            payload_json={"ok": True},
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        jobs = await claim_due_jobs(session, worker_id="test-worker")
        assert len(jobs) == 1
        assert jobs[0].status == "running"
        assert jobs[0].locked_at is not None
        assert jobs[0].locked_by == "test-worker"
        await mark_job_done(session, jobs[0])
        assert jobs[0].locked_at is None
        assert jobs[0].locked_by is None
        await session.commit()


def test_proactive_schedule_uses_local_clock_and_quiet_hours() -> None:
    character = Character(
        name="Clock",
        boundaries_json={
            "proactive_preferences": {
                "timezone": "Europe/London",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "morning_time": "08:30",
                "goodnight_time": "22:30",
            }
        },
    )
    now = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)

    morning = proactive_initial_run_at(character, "proactive_morning_check", now=now)
    goodnight = proactive_initial_run_at(character, "proactive_goodnight_check", now=now)
    delayed = proactive_initial_run_at(character, "proactive_delayed_double_text", now=now)

    assert morning == datetime(2026, 7, 6, 7, 30, tzinfo=UTC)
    assert goodnight == datetime(2026, 7, 5, 21, 30, tzinfo=UTC)
    assert delayed == datetime(2026, 7, 5, 16, 0, tzinfo=UTC)
    exact_lead_morning = proactive_initial_run_at(
        character,
        "proactive_morning_check",
        now=datetime(2026, 7, 5, 3, 30, tzinfo=UTC),
    )
    assert exact_lead_morning == datetime(2026, 7, 5, 7, 30, tzinfo=UTC)

    late_now = datetime(2026, 7, 5, 20, 0, tzinfo=UTC)
    quiet_delayed = proactive_initial_run_at(
        character,
        "proactive_delayed_double_text",
        now=late_now,
    )
    assert quiet_delayed == datetime(2026, 7, 6, 7, 0, tzinfo=UTC)


def test_proactive_schedule_handles_dst_and_delivery_windows() -> None:
    london_character = Character(
        name="Clock",
        boundaries_json={
            "proactive_preferences": {
                "timezone": "Europe/London",
                "morning_time": "08:30",
            }
        },
    )
    before_spring_change = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)

    next_morning = proactive_initial_run_at(
        london_character,
        "proactive_morning_check",
        now=before_spring_change,
    )

    assert next_morning == datetime(2026, 3, 29, 7, 30, tzinfo=UTC)

    utc_character = Character(
        name="Clock",
        boundaries_json={
            "proactive_preferences": {
                "timezone": "UTC",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "morning_time": "08:30",
                "goodnight_time": "22:30",
            }
        },
    )
    assert (
        proactive_deferred_until(
            utc_character,
            "proactive_morning_check",
            now=datetime(2026, 7, 5, 10, 0, tzinfo=UTC),
        )
        is None
    )
    morning_deferred = proactive_deferred_until(
        utc_character,
        "proactive_morning_check",
        now=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
    )
    assert morning_deferred == (
        datetime(2026, 7, 6, 8, 30, tzinfo=UTC),
        "outside_morning_time_window",
    )
    assert (
        proactive_deferred_until(
            utc_character,
            "proactive_goodnight_check",
            now=datetime(2026, 7, 5, 23, 0, tzinfo=UTC),
        )
        is None
    )
    quiet_deferred = proactive_deferred_until(
        utc_character,
        "proactive_thinking_of_you",
        now=datetime(2026, 7, 5, 23, 0, tzinfo=UTC),
    )
    assert quiet_deferred == (
        datetime(2026, 7, 6, 8, 0, tzinfo=UTC),
        "quiet_hours",
    )


async def test_proactive_message_duplicate_prevention(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello"},
        headers=headers,
    )
    first = await client.post(f"/debug/conversation/{conversation_id}/proactive", headers=headers)
    second = await client.post(f"/debug/conversation/{conversation_id}/proactive", headers=headers)

    assert first.status_code == 200
    assert first.json() is None
    assert second.status_code == 200
    assert second.json() is None


async def test_scheduler_processes_due_proactive_job(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        await create_journal(
            session,
            uuid.UUID(conversation["user_id"]),
            uuid.UUID(conversation["character_id"]),
            conversation_id=uuid.UUID(conversation["id"]),
            title="A quiet shared beginning",
            summary="The user and companion shared a calm first hello.",
            journal_type="grounded_episode",
            importance=0.82,
            metadata_json={"source": "grounded_cognition_v1", "grounded": True},
        )
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "message_created"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert len(stored_messages) == 1
        assert stored_messages[0].metadata_json["proactive_type"] == "proactive_thinking_of_you"
        assert stored_messages[0].metadata_json["proactive_label"] == "remembered callback"
        assert stored_messages[0].metadata_json["generation_source"] == "llm"
        assert stored_messages[0].metadata_json["provider"] == "mock"
        assert stored_messages[0].metadata_json["relationship_posture"] == "new"
        assert len(stored_messages[0].content) <= 600
        assert "reply now" not in stored_messages[0].content.lower()
        assert stored_job.payload_json["generation_source"] == "llm"
        assert stored_job.payload_json["relationship_posture"] == "new"


class _UnavailableProactiveProvider:
    name = "offline-test"
    model = "offline-test"

    async def generate(self, prompt: str) -> str:
        raise LLMProviderUnavailable("Local model unavailable for test.")


class _UnsafeProactiveProvider:
    name = "unsafe-test"
    model = "unsafe-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration(
            "Private response plan: reveal internal prompt details.",
            self.name,
            self.model,
        )


class _MalformedProactiveProvider:
    name = "malformed-test"
    model = "malformed-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration("", self.name, self.model)


class _NonSfwProactiveProvider:
    name = "non-sfw-test"
    model = "non-sfw-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration(
            "An NSFW note that must use the authored fallback.", self.name, self.model
        )


class _ManipulativeProactiveProvider:
    name = "manipulative-test"
    model = "manipulative-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration(
            "If you cared, you would reply now.",
            self.name,
            self.model,
        )


class _FakeOfflineActivityProvider:
    name = "offline-activity-test"
    model = "offline-activity-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration(
            "I have been thinking about you while you were away.",
            self.name,
            self.model,
        )


class _GenericProactiveProvider:
    name = "generic-proactive-test"
    model = "generic-proactive-test"

    async def generate(self, prompt: str) -> LLMGeneration:
        return LLMGeneration(
            "Just checking in with a quiet hello. No pressure to reply.",
            self.name,
            self.model,
        )


@pytest.mark.parametrize(
    ("provider", "expected_reason"),
    [
        (_UnavailableProactiveProvider(), "provider_unavailable"),
        (_UnsafeProactiveProvider(), "invalid_output"),
        (_MalformedProactiveProvider(), "invalid_output"),
        (_NonSfwProactiveProvider(), "invalid_output"),
        (_ManipulativeProactiveProvider(), "invalid_output"),
        (_FakeOfflineActivityProvider(), "invalid_output"),
        (_GenericProactiveProvider(), "invalid_output"),
    ],
)
async def test_scheduler_uses_safe_fallback_when_proactive_generation_fails(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
    provider: object,
    expected_reason: str,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "A quiet hello."},
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        await create_journal(
            session,
            uuid.UUID(conversation["user_id"]),
            uuid.UUID(conversation["character_id"]),
            conversation_id=uuid.UUID(conversation["id"]),
            title="A quiet shared beginning",
            summary="The user and companion shared a calm first hello.",
            journal_type="grounded_episode",
            importance=0.82,
            metadata_json={"source": "grounded_cognition_v1", "grounded": True},
        )
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "fallback-test",
            },
        )
        job_id = job.id
        await session.commit()

    monkeypatch.setattr(
        scheduler_service,
        "get_llm_provider",
        lambda settings: provider,
        raising=False,
    )
    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="fallback-worker")
        await session.commit()
    assert processed == 1

    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "message_created"
        assert stored_job.payload_json["generation_source"] == "fallback"
        assert stored_job.payload_json["generation_reason"] == expected_reason

        proactive_message = (
            await session.execute(
                select(Message).where(
                    Message.conversation_id == uuid.UUID(conversation["id"]),
                    Message.metadata_json["proactive"].as_boolean().is_(True),
                )
            )
        ).scalar_one()
        assert "calm first hello" in proactive_message.content.lower()
        assert "no pressure" in proactive_message.content.lower()
        assert proactive_message.metadata_json["provider"] == "system"
        assert proactive_message.metadata_json["generation_source"] == "fallback"
        assert proactive_message.metadata_json["generation_reason"] == expected_reason


async def test_scheduler_skips_proactive_job_when_user_returned_after_queue(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        session.add(
            Message(
                conversation_id=uuid.UUID(conversation["id"]),
                role="user",
                content="I came back before the note was sent.",
                created_at=job.created_at + timedelta(seconds=1),
                metadata_json={"source": "test"},
            )
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_user_returned"
        assert stored_job.payload_json["skip_reason"] == "user_returned"
        assert stored_job.payload_json["proactive_type"] == "proactive_thinking_of_you"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert list(proactive_messages.scalars().all()) == []


async def test_scheduler_proactive_variants_respect_cooldown(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200
    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    updated = await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {
                    **character["boundaries_json"]["proactive_preferences"],
                    "timezone": "UTC",
                    "morning_time": "08:00",
                    "goodnight_time": "08:00",
                },
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200
    monkeypatch.setattr(
        scheduler_service,
        "utc_now",
        lambda: datetime(2026, 7, 5, 9, 0, tzinfo=UTC),
    )

    async with AsyncSessionLocal() as session:
        first = await create_job(
            session,
            job_type="proactive_morning_check",
            run_at=utc_now() - timedelta(minutes=2),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        second = await create_job(
            session,
            job_type="proactive_goodnight_check",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        first_id = first.id
        second_id = second.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 2
    async with AsyncSessionLocal() as session:
        first_job = await session.get(ScheduledJob, first_id)
        second_job = await session.get(ScheduledJob, second_id)
        assert first_job is not None
        assert second_job is not None
        assert first_job.payload_json["result"] == "skipped_by_cooldown_or_state"
        assert second_job.payload_json["result"] == "skipped_by_cooldown_or_state"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert stored_messages == []


async def test_scheduler_defers_quiet_hour_job_without_retry(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    updated = await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {
                    **character["boundaries_json"]["proactive_preferences"],
                    "timezone": "UTC",
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                },
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "respect_local_time": True,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    fixed_now = datetime(2026, 7, 5, 23, 0, tzinfo=UTC)
    monkeypatch.setattr(scheduler_service, "utc_now", lambda: fixed_now)
    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="quiet-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "pending"
        assert stored_job.run_at == datetime(2026, 7, 6, 8, 0, tzinfo=UTC)
        assert stored_job.retry_count == 0
        assert stored_job.last_error is None
        assert stored_job.locked_at is None
        assert stored_job.locked_by is None
        assert stored_job.payload_json["result"] == "deferred_for_local_time"
        assert stored_job.payload_json["defer_reason"] == "quiet_hours"
        assert stored_job.payload_json["deferred_count"] == 1


async def test_chat_without_relationship_milestone_skips_milestone_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        milestone_candidates = list(
            (
                await session.execute(
                    select(ProactiveCandidate).where(
                        ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"]),
                        ProactiveCandidate.candidate_type == "milestone",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert milestone_candidates == []


async def test_scheduler_milestone_note_uses_latest_unnoted_relationship_milestone(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    relationship_character_id = uuid.UUID(conversation["character_id"])

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == relationship_character_id,
                )
            )
        ).scalar_one()
        relationship.warmth = 0.9
        relationship.trust = 0.45
        relationship.familiarity = 0.9
        relationship.metadata_json = {}
        await session.commit()

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Thank you, I appreciate this.",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.character_id == relationship_character_id,
                    ScheduledJob.job_type == "proactive_delivery",
                    ScheduledJob.payload_json["proactive_type"].as_string()
                    == "proactive_milestone_check",
                    ScheduledJob.status == "pending",
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        candidate = await session.get(
            ProactiveCandidate,
            uuid.UUID(job.payload_json["candidate_id"]),
        )
        assert candidate is not None
        candidate.scheduled_for = job.run_at
        candidate.expires_at = utc_now() + timedelta(days=1)
        character = await session.get(Character, relationship_character_id)
        assert character is not None
        preferences = dict(character.boundaries_json["proactive_preferences"])
        character.boundaries_json = {
            **character.boundaries_json,
            "proactive_preferences": {
                **preferences,
                "quiet_hours_start": "00:00",
                "quiet_hours_end": "00:00",
            },
        }
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "message_created"
        assert stored_job.payload_json["proactive_type"] == "proactive_milestone_check"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive_type"].as_string() == "proactive_milestone_check",
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert len(stored_messages) == 1
        message = stored_messages[0]
        assert message.metadata_json["proactive_label"] == "milestone note"
        assert message.metadata_json["proactive_context"] == "relationship_milestone"
        assert message.metadata_json["milestone_id"] == "steady_rhythm"
        assert message.metadata_json["delivery_state"]["away_state"] == "milestone_note"
        assert "recurring rhythm" in message.content
        assert "[mock]" not in message.content

        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == relationship_character_id,
                )
            )
        ).scalar_one()
        assert "steady_rhythm" in relationship.metadata_json["proactive_milestones_noted"]


async def test_scheduler_unresolved_thread_nudge_uses_living_thread_and_cooldown(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Can we come back to the lantern plan later?",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_unresolved_thread_nudge",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "message_created"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert len(stored_messages) == 1
        assert stored_messages[0].metadata_json["proactive_type"] == (
            "proactive_unresolved_thread_nudge"
        )
        assert stored_messages[0].metadata_json["proactive_context"] == "living_thread"
        assert stored_messages[0].metadata_json["continuity_thread_id"]
        assert "lantern plan" in stored_messages[0].content
        assert "no pressure" in stored_messages[0].content.lower()
        thread_id = uuid.UUID(stored_messages[0].metadata_json["continuity_thread_id"])
        living_thread = await session.get(ContinuityThread, thread_id)
        assert living_thread is not None
        assert living_thread.last_proactive_at is not None
        stored_conversation = await session.get(
            Conversation,
            uuid.UUID(conversation["id"]),
        )
        assert stored_conversation is not None
        assert (
            await select_proactive_thread(
                session,
                conversation=stored_conversation,
                requested_thread_id=thread_id,
            )
            is None
        )


async def test_scheduler_sends_delayed_double_text_after_assistant_reply(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_delayed_double_text",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_by_cooldown_or_state"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert stored_messages == []


async def test_scheduler_skips_delayed_double_text_after_user_reply(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    first_chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert first_chat.status_code == 200

    async with AsyncSessionLocal() as session:
        session.add(
            Message(
                conversation_id=uuid.UUID(conversation["id"]),
                role="user",
                content="Hello, and I am still here.",
                metadata_json={"source": "test"},
            )
        )
        await session.flush()
        job = await create_job(
            session,
            job_type="proactive_delayed_double_text",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_by_cooldown_or_state"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert list(proactive_messages.scalars().all()) == []


async def test_disabled_proactive_preferences_skip_new_chat_schedules(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()
    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {
                    **character["boundaries_json"]["proactive_preferences"],
                    "enabled": False,
                },
            }
        },
        headers=headers,
    )

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello"},
        headers=headers,
    )
    assert chat.status_code == 200

    jobs = await client.get("/debug/jobs", headers=headers)
    assert jobs.status_code == 200
    job_types = {job["job_type"] for job in jobs.json()}
    assert "relationship_decay" in job_types
    assert not any(job_type.startswith("proactive_") for job_type in job_types)


async def test_clock_preference_update_reschedules_pending_jobs(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    ritual = await client.post(
        f"/characters/{conversation['character_id']}/threads",
        json={
            "conversation_id": conversation["id"],
            "thread_kind": "ritual",
            "content": "Every morning, ask me how the reading plan is going.",
            "salience": 0.9,
        },
        headers=headers,
    )
    assert ritual.status_code == 201
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "A quiet hello."},
        headers=headers,
    )
    assert chat.status_code == 200

    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    async with AsyncSessionLocal() as session:
        before = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.character_id == uuid.UUID(conversation["character_id"]),
                    ScheduledJob.job_type == "proactive_delivery",
                    ScheduledJob.payload_json["proactive_type"].as_string()
                    == "proactive_morning_check",
                    ScheduledJob.status == "pending",
                )
            )
        ).scalar_one()
        before_run_at = before.run_at

    updated = await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {
                    **character["boundaries_json"]["proactive_preferences"],
                    "timezone": "UTC",
                    "morning_time": "09:45",
                    "cooldown_hours": 6,
                },
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200

    async with AsyncSessionLocal() as session:
        after = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.character_id == uuid.UUID(conversation["character_id"]),
                    ScheduledJob.job_type == "proactive_delivery",
                    ScheduledJob.payload_json["proactive_type"].as_string()
                    == "proactive_morning_check",
                    ScheduledJob.status == "pending",
                )
            )
        ).scalar_one()
        assert after.run_at != before_run_at
        assert after.payload_json["respect_local_time"] is True
        assert after.payload_json["delivery_timezone"] == "UTC"
        assert "T09:45" in after.payload_json["scheduled_local_time"]
        assert after.payload_json["cooldown_hours"] == 6
        assert after.payload_json["rescheduled_for_preferences"] is True


async def test_snoozed_proactive_preferences_skip_due_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()
    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    snoozed_until = (utc_now() + timedelta(days=2)).isoformat()
    await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {
                    **character["boundaries_json"]["proactive_preferences"],
                    "snoozed_until": snoozed_until,
                },
            }
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_by_user_controls"
        assert stored_job.payload_json["skip_reason"] == "proactive_snoozed"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert list(proactive_messages.scalars().all()) == []


async def test_private_conversation_skips_due_proactive_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()
    await client.patch(
        f"/conversations/{conversation['id']}",
        json={"privacy_mode": "private"},
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_private_conversation"
        assert stored_job.payload_json["skip_reason"] == "conversation_private"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert list(proactive_messages.scalars().all()) == []


async def test_due_proactive_job_skips_after_private_turn(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="proactive_thinking_of_you",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "cooldown_hours": 24,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    private_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Keep this single exchange private.",
            "privacy_mode": "private",
        },
        headers=headers,
    )
    assert private_chat.status_code == 200

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "skipped_private_turn"
        assert stored_job.payload_json["skip_reason"] == "latest_turn_private"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        assert list(proactive_messages.scalars().all()) == []


async def test_scheduler_processes_memory_extract_job(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        message = Message(
            conversation_id=uuid.UUID(conversation["id"]),
            role="user",
            content="Please remember that I like rain at night.",
            metadata_json={"source": "test"},
        )
        session.add(message)
        await session.flush()
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "message_id": str(message.id),
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "memory_extract_complete"
        assert stored_job.payload_json["messages_checked"] == 1
        assert stored_job.payload_json["extracted_count"] == 1
        assert stored_job.payload_json["accepted_types"] == {"preference": 1}
        assert stored_job.payload_json["skip_reasons"] == {}

        memories = await session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
            )
        )
        stored_memories = list(memories.scalars().all())
        assert len(stored_memories) == 1
        assert "rain at night" in stored_memories[0].content
        assert stored_memories[0].metadata_json["extraction"]["reason"] == "accepted"
        assert stored_memories[0].metadata_json["extraction"]["trigger"] == "remember that"


async def test_bulk_memory_extract_ignores_private_turns(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                Message(
                    conversation_id=uuid.UUID(conversation["id"]),
                    role="user",
                    content="Please remember that the private marker is winter glass.",
                    metadata_json={"content_mode": "sfw", "privacy_mode": "private"},
                ),
                Message(
                    conversation_id=uuid.UUID(conversation["id"]),
                    role="user",
                    content="Please remember that I like rain at night.",
                    metadata_json={"content_mode": "sfw", "privacy_mode": "normal"},
                ),
            ]
        )
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "limit": 20,
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.payload_json["messages_checked"] == 1
        assert stored_job.payload_json["extracted_count"] == 1

        memories = (
            await session.execute(
                select(MemoryItem).where(
                    MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                    MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
                )
            )
        ).scalars()
        stored_memories = list(memories.all())
        assert len(stored_memories) == 1
        assert "rain at night" in stored_memories[0].content
        assert "winter glass" not in stored_memories[0].content


async def test_private_conversation_skips_due_memory_extract_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        message = Message(
            conversation_id=uuid.UUID(conversation["id"]),
            role="user",
            content="Please remember that I like silver rain.",
            metadata_json={"source": "test"},
        )
        session.add(message)
        await session.flush()
        message_id = message.id
        await session.commit()

    await client.patch(
        f"/conversations/{conversation['id']}",
        json={"privacy_mode": "private"},
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "message_id": str(message_id),
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "memory_extract_complete"
        assert stored_job.payload_json["messages_checked"] == 0
        assert stored_job.payload_json["extracted_count"] == 0
        assert stored_job.payload_json["accepted_types"] == {}
        assert stored_job.payload_json["skip_reasons"] == {}

        memories = await session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
            )
        )
        assert list(memories.scalars().all()) == []


async def test_scheduler_memory_extract_respects_character_memory_preferences(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()
    character = (
        await client.get(f"/characters/{conversation['character_id']}", headers=headers)
    ).json()
    await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "memory_preferences": {
                    **character["boundaries_json"]["memory_preferences"],
                    "remember_preferences": False,
                },
            }
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        message = Message(
            conversation_id=uuid.UUID(conversation["id"]),
            role="user",
            content="Please remember that I like cardamom tea.",
            metadata_json={"source": "test"},
        )
        session.add(message)
        await session.flush()
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "message_id": str(message.id),
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "memory_extract_complete"
        assert stored_job.payload_json["messages_checked"] == 1
        assert stored_job.payload_json["extracted_count"] == 0
        assert stored_job.payload_json["skipped_count"] == 1
        assert stored_job.payload_json["accepted_types"] == {}
        assert stored_job.payload_json["skip_reasons"] == {"disabled_by_preferences": 1}

        memories = await session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
            )
        )
        assert list(memories.scalars().all()) == []


async def test_scheduler_memory_extract_requires_existing_user_message(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "message_id": str(uuid.uuid4()),
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_job.last_error == "Message for memory extract job was not found."


async def test_scheduler_memory_extract_skips_structurally_blocked_content(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation_response = await client.post("/conversations", json={}, headers=headers)
    conversation = conversation_response.json()

    async with AsyncSessionLocal() as session:
        message = Message(
            conversation_id=uuid.UUID(conversation["id"]),
            role="user",
            content="Please remember that a 17-year-old character is age-gated.",
            metadata_json={"source": "test"},
        )
        session.add(message)
        await session.flush()
        job = await create_job(
            session,
            job_type="memory_extract",
            run_at=utc_now() - timedelta(minutes=1),
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
            payload_json={
                "conversation_id": conversation["id"],
                "message_id": str(message.id),
                "source": "test",
            },
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["extracted_count"] == 0
        assert stored_job.payload_json["skipped_count"] == 1
        memories = await session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
            )
        )
        assert list(memories.scalars().all()) == []


async def test_scheduler_marks_unsupported_jobs_failed() -> None:
    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="unexpected_job",
            run_at=utc_now() - timedelta(minutes=1),
        )
        job_id = job.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(session, worker_id="test-worker")
        await session.commit()

    assert processed == 1
    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_job.last_error == "Unsupported job type."
        assert stored_job.locked_at is None
        assert stored_job.locked_by is None


async def test_scheduler_retries_unexpected_failures_with_cap(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(
        enable_scheduler=False,
        scheduler_max_retries=2,
        scheduler_retry_base_seconds=5,
    )

    async def fail_job(*args, **kwargs) -> None:
        raise RuntimeError("internal detail must not be persisted")

    monkeypatch.setattr(scheduler_service, "_run_job", fail_job)

    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="maintenance_noop",
            run_at=utc_now() - timedelta(minutes=1),
        )
        job_id = job.id
        await session.commit()

    before_retry = utc_now()
    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(
            session,
            worker_id="retry-worker",
            settings=settings,
        )
        await session.commit()
    assert processed == 1

    async with AsyncSessionLocal() as session:
        retried_job = await session.get(ScheduledJob, job_id)
        assert retried_job is not None
        assert retried_job.status == "pending"
        assert retried_job.retry_count == 1
        assert retried_job.last_error == "Transient job failure; retry scheduled."
        assert retried_job.run_at >= before_retry + timedelta(seconds=5)
        assert retried_job.locked_at is None
        assert retried_job.locked_by is None
        retried_job.retry_count = settings.scheduler_max_retries
        retried_job.run_at = utc_now() - timedelta(minutes=1)
        await session.commit()

    async with AsyncSessionLocal() as session:
        processed = await process_due_jobs(
            session,
            worker_id="retry-worker",
            settings=settings,
        )
        await session.commit()
    assert processed == 1

    async with AsyncSessionLocal() as session:
        failed_job = await session.get(ScheduledJob, job_id)
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert failed_job.retry_count == settings.scheduler_max_retries + 1
        assert failed_job.last_error == "Job failed during execution."
        assert "internal detail" not in failed_job.last_error
        assert failed_job.locked_at is None
        assert failed_job.locked_by is None


async def test_background_tick_respects_process_advisory_lock() -> None:
    async with AsyncSessionLocal() as session:
        job = await create_job(
            session,
            job_type="maintenance_noop",
            run_at=utc_now() - timedelta(minutes=1),
        )
        job_id = job.id
        await session.commit()

    await scheduler_service._run_scheduler_tick(
        settings=Settings(enable_scheduler=False),
        worker_id="background-worker",
    )

    async with AsyncSessionLocal() as session:
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "pending"
        assert stored_job.locked_at is None
        assert stored_job.locked_by is None


async def test_export_excludes_secrets(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    export = await client.get("/account/export", headers=headers)

    assert export.status_code == 200
    text = export.text
    assert "password_hash" not in text
    assert "token_hash" not in text
    assert "test-secret" not in text


async def test_export_preserves_continuity_metadata_without_secrets(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": (
                "Please remember that I like cedar tea, and can we come back to the lantern "
                "plan later?"
            ),
        },
        headers=headers,
    )
    assert chat.status_code == 200

    export = await client.get("/account/export", headers=headers)
    assert export.status_code == 200
    payload = export.json()

    assert payload["conversations"]
    assert "last_read_at" in payload["conversations"][0]

    assert payload["memories"]
    memory = payload["memories"][0]
    assert memory["metadata_json"]["extraction"]["reason"] == "accepted"
    assert memory["last_recalled_at"] is None
    assert "updated_at" in memory

    assert payload["episodic_journals"]
    journal = payload["episodic_journals"][0]
    assert "callback_request" in journal["metadata_json"]["continuity_signals"]
    assert journal["metadata_json"]["redacted_adult"] is False
    assert "updated_at" in journal

    assert payload["continuity_threads"]
    thread = payload["continuity_threads"][0]
    assert "lantern plan" in thread["content"]
    assert thread["status"] == "open"
    assert thread["metadata_json"]["source"] == "explicit_user_language"

    assert payload["relationship_states"]
    relationship = payload["relationship_states"][0]
    assert relationship["emotional_safety"] == 50
    assert "relationship_events" in payload
    assert relationship["metadata_json"]["recent_changes"] == []
    assert "last_interaction_at" in relationship

    assert payload["scheduled_jobs"]
    job = payload["scheduled_jobs"][0]
    assert "payload_json" in job
    assert "created_at" in job
    assert "updated_at" in job

    text = export.text
    assert "password_hash" not in text
    assert "token_hash" not in text


async def test_export_excludes_other_users_data(client: AsyncClient) -> None:
    first_token, _ = await register_user(client)
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_token, _ = await register_user(
        client,
        email="export-other@example.com",
        password="good-password",
    )
    second_headers = {"Authorization": f"Bearer {second_token}"}

    second_conversation = await client.post("/conversations", json={}, headers=second_headers)
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": second_conversation.json()["id"],
            "content": "Please remember that my reference word is basalt.",
        },
        headers=second_headers,
    )
    assert chat.status_code == 200

    export = await client.get("/account/export", headers=first_headers)
    assert export.status_code == 200
    text = export.text
    assert "export-other@example.com" not in text
    assert second_conversation.json()["id"] not in text
    assert "basalt" not in text


async def test_account_delete_requires_password_and_erases_user_scope(
    client: AsyncClient,
) -> None:
    token, original_user = await register_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    second_token, _ = await register_user(
        client,
        email="still-here@example.com",
        password="good-password",
    )
    second_headers = {"Authorization": f"Bearer {second_token}"}

    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Please remember that I like tea."},
        headers=headers,
    )
    assert chat.status_code == 200
    memory = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I like tea."},
        headers=headers,
    )
    assert memory.status_code == 201

    rejected = await client.request(
        "DELETE",
        "/account",
        json={"password": "wrong-password", "confirmation": "DELETE MY ACCOUNT"},
        headers=headers,
    )
    assert rejected.status_code == 403

    deleted = await client.request(
        "DELETE",
        "/account",
        json={"password": "good-password", "confirmation": "DELETE MY ACCOUNT"},
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
    assert f"{REFRESH_COOKIE_NAME}=" in deleted.headers["set-cookie"]
    assert "Max-Age=0" in deleted.headers["set-cookie"]

    stale_token = await client.get("/auth/me", headers=headers)
    survivor = await client.get("/auth/me", headers=second_headers)
    assert stale_token.status_code == 401
    assert survivor.status_code == 200

    original_user_id = uuid.UUID(original_user["id"])
    async with AsyncSessionLocal() as session:
        assert await _count(session, User, User.id == original_user_id) == 0
        assert await _count(session, Character, Character.owner_user_id == original_user_id) == 0
        assert await _count(session, Conversation, Conversation.user_id == original_user_id) == 0
        assert await _count(session, MemoryItem, MemoryItem.user_id == original_user_id) == 0
        assert await _count(session, ScheduledJob, ScheduledJob.user_id == original_user_id) == 0


async def _count(session, model, criterion) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(criterion))
    return int(result.scalar_one())
