from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

from helpers import auth_headers, register_user
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select

from app.config import Settings
from app.db.session import AsyncSessionLocal
from app.llm.base import LLMGeneration
from app.models import (
    Character,
    ContinuityThread,
    Conversation,
    MemoryItem,
    Message,
    ProactiveCandidate,
    ProactiveCandidateEvent,
    ScheduledJob,
    utc_now,
)
from app.services import scheduler as scheduler_service
from app.services.jobs import claim_due_jobs
from app.services.proactive_presence import (
    cancel_pending_for_character,
    deliver_proactive_candidate,
    ensure_proactive_candidates,
    mark_delivered_candidates_replied,
    memory_source_version,
)
from app.services.response_planner import list_pending_proactive_events
from app.services.scheduler import process_due_jobs


class _BlockingProactiveProvider:
    name = "blocking-test"
    model = "blocking-test"

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, _prompt: str) -> LLMGeneration:
        self.started.set()
        await self.release.wait()
        return LLMGeneration(
            content="We can return to reviewing your notes whenever it is useful.",
            provider=self.name,
            model=self.model,
        )


async def test_generic_chat_does_not_create_timer_only_candidates(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()

    response = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "Hello."},
        headers=headers,
    )

    assert response.status_code == 200
    async with AsyncSessionLocal() as session:
        candidates = list(
            (
                await session.execute(
                    select(ProactiveCandidate).where(
                        ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
        proactive_jobs = list(
            (
                await session.execute(
                    select(ScheduledJob).where(ScheduledJob.job_type == "proactive_delivery")
                )
            )
            .scalars()
            .all()
        )
    assert candidates == []
    assert proactive_jobs == []


async def test_explicit_reminder_uses_unified_delivery_lifecycle(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    thread = await client.post(
        f"/characters/{conversation['character_id']}/threads",
        json={
            "conversation_id": conversation["id"],
            "thread_kind": "follow_up",
            "content": "Remind me tomorrow at 3pm to review my notes.",
            "salience": 0.9,
        },
        headers=headers,
    )
    assert thread.status_code == 201

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "I am heading out for now.",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    async with AsyncSessionLocal() as session:
        candidates = list(
            (
                await session.execute(
                    select(ProactiveCandidate).where(
                        ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.candidate_type == "reminder"
        assert candidate.initiative_kind == "reminder"
        assert candidate.state == "scheduled"
        assert candidate.continuity_thread_id == uuid.UUID(thread.json()["id"])
        assert candidate.notification_preview == "New companion note"
        assert "review my notes" not in candidate.notification_preview
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                )
            )
        ).scalar_one()
        assert job.job_type == "proactive_delivery"
        assert job.dedupe_key == f"proactive-delivery:{candidate.id}"
        original_schedule = candidate.scheduled_for
        stored_character = (
            await client.get(
                f"/characters/{conversation['character_id']}",
                headers=headers,
            )
        ).json()
        profile = dict(stored_character["boundaries_json"])
        preferences = dict(profile["proactive_preferences"])
        preferences["cooldown_hours"] = 72
        preference_update = await client.patch(
            f"/characters/{conversation['character_id']}",
            json={
                "boundaries_json": {
                    **profile,
                    "proactive_preferences": preferences,
                }
            },
            headers=headers,
        )
        assert preference_update.status_code == 200
        await session.refresh(candidate)
        await session.refresh(job)
        assert candidate.scheduled_for == original_schedule
        assert job.run_at == original_schedule
        pause_until = utc_now() + timedelta(days=2)
        paused_preferences = dict(
            preference_update.json()["boundaries_json"]["proactive_preferences"]
        )
        paused = await client.patch(
            f"/characters/{conversation['character_id']}",
            json={
                "boundaries_json": {
                    **preference_update.json()["boundaries_json"],
                    "proactive_preferences": {
                        **paused_preferences,
                        "snoozed_until": pause_until.isoformat(),
                    },
                }
            },
            headers=headers,
        )
        assert paused.status_code == 200
        await session.refresh(candidate)
        await session.refresh(job)
        assert candidate.scheduled_for == pause_until
        assert job.run_at == pause_until
        resumed = await client.patch(
            f"/characters/{conversation['character_id']}",
            json={
                "boundaries_json": {
                    **paused.json()["boundaries_json"],
                    "proactive_preferences": {
                        **paused.json()["boundaries_json"]["proactive_preferences"],
                        "snoozed_until": None,
                    },
                }
            },
            headers=headers,
        )
        assert resumed.status_code == 200
        await session.refresh(candidate)
        await session.refresh(job)
        assert candidate.scheduled_for == original_schedule
        assert job.run_at == original_schedule
        stored_conversation = await session.get(
            Conversation,
            uuid.UUID(conversation["id"]),
        )
        assert stored_conversation is not None
        duplicate = await ensure_proactive_candidates(
            session,
            conversation=stored_conversation,
            user_id=uuid.UUID(conversation["user_id"]),
            character_id=uuid.UUID(conversation["character_id"]),
        )
        assert duplicate == []
        candidate.scheduled_for = utc_now() - timedelta(minutes=1)
        job.run_at = candidate.scheduled_for
        candidate.expires_at = utc_now() + timedelta(days=1)
        await session.commit()
        candidate_id = candidate.id

    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="presence-test") == 1
        await session.commit()

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "delivered"
        assert candidate.message_id is not None
        message = await session.get(Message, candidate.message_id)
        assert message is not None
        assert message.metadata_json["proactive_candidate_id"] == str(candidate.id)
        assert message.metadata_json["initiative_kind"] == "reminder"
        states = list(
            (
                await session.execute(
                    select(ProactiveCandidateEvent.to_state)
                    .where(ProactiveCandidateEvent.candidate_id == candidate.id)
                    .order_by(ProactiveCandidateEvent.created_at)
                )
            )
            .scalars()
            .all()
        )
    assert states == ["candidate", "scheduled", "generated", "delivered"]


async def test_inbox_open_dismiss_and_mute_feedback_are_owner_scoped(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    candidate_id, conversation = await _delivered_follow_up(client, headers)

    inbox = await client.get(
        f"/proactive?view=inbox&character_id={conversation['character_id']}",
        headers=headers,
    )
    assert inbox.status_code == 200
    assert len(inbox.json()) == 1
    item = inbox.json()[0]
    assert item["state"] == "delivered"
    assert item["notification_preview"] == "New companion note"
    assert item["message_preview"]

    opened = await client.post(f"/proactive/{candidate_id}/open", headers=headers)
    assert opened.status_code == 200
    assert opened.json()["state"] == "opened"
    dismissed = await client.post(
        f"/proactive/{candidate_id}/dismiss",
        json={"feedback": "mute_similar"},
        headers=headers,
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["state"] == "dismissed"
    assert dismissed.json()["dismissal_feedback"] == "mute_similar"

    character = await client.get(
        f"/characters/{conversation['character_id']}",
        headers=headers,
    )
    assert (
        "follow_up"
        in character.json()["boundaries_json"]["proactive_preferences"]["muted_categories"]
    )
    other_token, _ = await register_user(
        client,
        email="other@example.com",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    forbidden = await client.post(f"/proactive/{candidate_id}/open", headers=other_headers)
    assert forbidden.status_code == 404


async def test_user_return_cancels_pending_note_and_records_return(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)

    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "I am back, and the plan changed.",
        },
        headers=headers,
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "replied"
        assert candidate.replied_at is not None
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                )
            )
        ).scalar_one()
        assert job.status == "cancelled"
        return_candidate = (
            await session.execute(
                select(ProactiveCandidate).where(
                    ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"]),
                    ProactiveCandidate.candidate_type == "return",
                )
            )
        ).scalar_one()
        assert return_candidate.state == "replied"
        current_labels = await list_pending_proactive_events(
            session,
            user_id=return_candidate.user_id,
            character_id=return_candidate.character_id,
            conversation_id=return_candidate.conversation_id,
            current_message_id=return_candidate.source_message_id,
        )
        later_labels = await list_pending_proactive_events(
            session,
            user_id=return_candidate.user_id,
            character_id=return_candidate.character_id,
            conversation_id=return_candidate.conversation_id,
            current_message_id=uuid.uuid4(),
        )
        debug_labels = await list_pending_proactive_events(
            session,
            user_id=return_candidate.user_id,
            character_id=return_candidate.character_id,
            conversation_id=return_candidate.conversation_id,
        )
        assert "return after a pending note" in current_labels
        assert "return after a pending note" not in later_labels
        assert "return after a pending note" not in debug_labels


async def test_user_can_cancel_one_pending_note_and_its_delivery_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    _, candidate_id = await _scheduled_follow_up(client, headers)

    response = await client.post(f"/proactive/{candidate_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    history = await client.get("/proactive?view=history", headers=headers)
    assert history.status_code == 200
    assert any(
        item["id"] == str(candidate_id) and item["state"] == "cancelled" for item in history.json()
    )

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.failure_code == "cancelled_by_user"
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        assert job.status == "cancelled"
        assert job.cancelled_at is not None
        assert job.last_error == "cancelled_by_user"


async def test_deleted_source_and_expired_candidate_are_suppressed(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        thread = await session.get(ContinuityThread, candidate.continuity_thread_id)
        assert thread is not None
        await session.delete(thread)
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        await session.commit()

    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="source-test") == 1
        await session.commit()
    async with AsyncSessionLocal() as session:
        stale = await session.get(ProactiveCandidate, candidate_id)
        assert stale is not None
        assert stale.state == "cancelled"
        assert stale.failure_code == "source_stale_or_deleted"

    second_conversation, second_id = await _scheduled_follow_up(client, headers)
    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, second_id)
        assert candidate is not None
        candidate.expires_at = utc_now() - timedelta(minutes=1)
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="expiry-test") == 1
        await session.commit()
    async with AsyncSessionLocal() as session:
        expired = await session.get(ProactiveCandidate, second_id)
        assert expired is not None
        assert expired.state == "expired"
        assert second_conversation["id"] != conversation["id"]


async def test_resolved_thread_immediately_cancels_its_pending_candidate(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None and candidate.continuity_thread_id is not None
        thread_id = candidate.continuity_thread_id

    response = await client.patch(
        f"/characters/{conversation['character_id']}/threads/{thread_id}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "continuity_source_changed"
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        assert job.status == "cancelled"


async def test_deleted_memory_source_is_revalidated_before_generation(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    _, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        memory = MemoryItem(
            user_id=candidate.user_id,
            character_id=candidate.character_id,
            source_message_id=candidate.source_message_id,
            memory_type="event",
            content="A general-context source that may later be forgotten.",
        )
        session.add(memory)
        await session.flush()
        candidate.memory_id = memory.id
        candidate.continuity_thread_id = None
        candidate.delivery_constraints_json = {
            **candidate.delivery_constraints_json,
            "required_source": "memory",
            "source_version": memory_source_version(memory),
        }
        memory_id = memory.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        memory = await session.get(MemoryItem, memory_id)
        assert memory is not None
        await session.delete(memory)
        await session.commit()

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        await session.commit()

    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="deleted-memory-test") == 1
        await session.commit()
    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "source_stale_or_deleted"


async def test_quiet_hours_defer_candidate_without_generating_copy(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    _, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        character = await session.get(Character, candidate.character_id)
        assert character is not None
        profile = dict(character.boundaries_json)
        preferences = dict(profile["proactive_preferences"])
        preferences["timezone"] = "UTC"
        preferences["quiet_hours_start"] = "22:00"
        preferences["quiet_hours_end"] = "07:00"
        character.boundaries_json = {
            **profile,
            "proactive_preferences": preferences,
        }
        candidate.expires_at = utc_now() + timedelta(days=2)
        await session.flush()
        result = await deliver_proactive_candidate(
            session,
            candidate_id=candidate_id,
            provider=None,
            now=utc_now().replace(hour=23, minute=30, second=0, microsecond=0),
        )
        assert result.status == "deferred"
        assert result.reason == "quiet_hours"
        assert result.deferred_until is not None
        assert result.deferred_until.hour == 7
        assert result.candidate.state == "scheduled"
        assert result.candidate.message_id is None
        await session.rollback()


async def test_daily_cap_suppresses_second_delivery(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    first_conversation, first_candidate_id = await _scheduled_follow_up(client, headers)
    _, second_candidate_id = await _scheduled_follow_up(
        client,
        headers,
        content="Please follow up about my garden plan next time.",
    )
    character = (
        await client.get(
            f"/characters/{first_conversation['character_id']}",
            headers=headers,
        )
    ).json()
    profile = dict(character["boundaries_json"])
    preferences = dict(profile["proactive_preferences"])
    preferences["daily_cap"] = 1
    preferences["quiet_hours_start"] = "00:00"
    preferences["quiet_hours_end"] = "00:00"
    updated = await client.patch(
        f"/characters/{first_conversation['character_id']}",
        json={
            "boundaries_json": {
                **profile,
                "proactive_preferences": preferences,
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200

    async with AsyncSessionLocal() as session:
        first_candidate = await session.get(ProactiveCandidate, first_candidate_id)
        assert first_candidate is not None
        first_candidate.scheduled_for = utc_now() - timedelta(minutes=1)
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(first_candidate_id)
                )
            )
        ).scalar_one()
        job.run_at = first_candidate.scheduled_for
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="daily-cap-first") == 1
        await session.commit()
    async with AsyncSessionLocal() as session:
        first_candidate = await session.get(ProactiveCandidate, first_candidate_id)
        assert first_candidate is not None
        assert first_candidate.state == "delivered", first_candidate.failure_code
        assert first_candidate.delivered_at is not None
        stored_character = await session.get(Character, first_candidate.character_id)
        assert stored_character is not None
        assert stored_character.boundaries_json["proactive_preferences"]["daily_cap"] == 1

    async with AsyncSessionLocal() as session:
        second_candidate = await session.get(ProactiveCandidate, second_candidate_id)
        assert second_candidate is not None
        second_candidate.scheduled_for = utc_now() - timedelta(minutes=1)
        second_job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string()
                    == str(second_candidate_id)
                )
            )
        ).scalar_one()
        second_job.run_at = second_candidate.scheduled_for
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="daily-cap-second") == 1
        await session.commit()
    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, second_candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "daily_cap_reached"


async def test_concurrent_workers_claim_one_candidate_once(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    _, candidate_id = await _scheduled_follow_up(client, headers)
    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        await session.commit()

    async def claim(worker_id: str) -> list[uuid.UUID]:
        async with AsyncSessionLocal() as session:
            jobs = await claim_due_jobs(session, worker_id=worker_id)
            await session.commit()
            return [job.id for job in jobs]

    claims = await asyncio.gather(claim("race-a"), claim("race-b"))
    assert sum(len(worker_claims) for worker_claims in claims) == 1


async def test_cancellation_does_not_deadlock_a_claimed_delivery_job(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as worker_session:
        job = (
            await worker_session.execute(
                select(ScheduledJob)
                .where(ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id))
                .with_for_update()
            )
        ).scalar_one()
        job.status = "running"
        job.locked_at = utc_now()
        job.locked_by = "worker-holding-job"
        await worker_session.flush()

        async with AsyncSessionLocal() as cancelling_session:
            cancelled = await asyncio.wait_for(
                cancel_pending_for_character(
                    cancelling_session,
                    character_id=uuid.UUID(conversation["character_id"]),
                    conversation_id=uuid.UUID(conversation["id"]),
                    reason_code="concurrent_user_return",
                ),
                timeout=2,
            )
            assert cancelled == 1
            await cancelling_session.commit()

        result = await deliver_proactive_candidate(
            worker_session,
            candidate_id=candidate_id,
            provider=None,
        )
        assert result.status == "already_terminal"
        assert result.candidate.state == "cancelled"
        await worker_session.rollback()


async def test_user_return_during_generation_suppresses_stale_delivery(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)
    provider = _BlockingProactiveProvider()

    async with AsyncSessionLocal() as delivery_session:
        delivery_task = asyncio.create_task(
            deliver_proactive_candidate(
                delivery_session,
                candidate_id=candidate_id,
                provider=provider,
            )
        )
        await asyncio.wait_for(provider.started.wait(), timeout=2)

        async with AsyncSessionLocal() as returning_session:
            stored_conversation = await returning_session.get(
                Conversation,
                uuid.UUID(conversation["id"]),
            )
            assert stored_conversation is not None
            user_message = Message(
                conversation_id=stored_conversation.id,
                role="user",
                content="I returned while that note was being prepared.",
                metadata_json={
                    "content_mode": "sfw",
                    "privacy_mode": "normal",
                    "streaming_complete": True,
                },
            )
            returning_session.add(user_message)
            await returning_session.flush()
            # The worker owns the candidate row, so the non-blocking return path
            # leaves the final stale-context check to the delivery transaction.
            assert (
                await mark_delivered_candidates_replied(
                    returning_session,
                    conversation=stored_conversation,
                    user_message=user_message,
                )
                == 0
            )
            await returning_session.commit()

        provider.release.set()
        result = await asyncio.wait_for(delivery_task, timeout=2)
        assert result.status == "suppressed"
        assert result.reason == "delivery_recheck_suppressed"
        await delivery_session.commit()

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        messages = list(
            (
                await session.execute(
                    select(Message).where(
                        Message.conversation_id == uuid.UUID(conversation["id"]),
                        Message.metadata_json["proactive_candidate_id"].as_string()
                        == str(candidate_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert messages == []


async def test_opt_out_cancels_pending_and_stale_worker_lock_is_recovered(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)

    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=20)
        job.status = "running"
        job.locked_at = utc_now() - timedelta(minutes=20)
        job.locked_by = "dead-worker"
        await session.commit()
    async with AsyncSessionLocal() as session:
        claimed = await claim_due_jobs(session, worker_id="replacement")
        assert [job.id for job in claimed]
        assert claimed[0].locked_by == "replacement"
        assert claimed[0].retry_count == 1
        await session.rollback()

    character = (
        await client.get(
            f"/characters/{conversation['character_id']}",
            headers=headers,
        )
    ).json()
    preferences = character["boundaries_json"]["proactive_preferences"]
    response = await client.patch(
        f"/characters/{conversation['character_id']}",
        json={
            "boundaries_json": {
                **character["boundaries_json"],
                "proactive_preferences": {**preferences, "enabled": False},
            }
        },
        headers=headers,
    )
    assert response.status_code == 200
    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "proactive_disabled"


async def test_contact_boundary_cancels_pending_notes_across_conversations(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    scheduled_conversation, candidate_id = await _scheduled_follow_up(client, headers)
    boundary_conversation = (
        await client.post(
            "/conversations",
            json={"character_id": scheduled_conversation["character_id"]},
            headers=headers,
        )
    ).json()
    response = await client.post(
        "/chat/messages",
        json={
            "conversation_id": boundary_conversation["id"],
            "content": "Please don't send me proactive messages. That is my boundary.",
        },
        headers=headers,
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "relationship_boundary"
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        assert job.status == "cancelled"


async def test_candidate_retry_backoff_reaches_safe_dead_letter(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await auth_headers(client)
    _, candidate_id = await _scheduled_follow_up(client, headers)

    async def fail_delivery(*args, **kwargs):
        raise RuntimeError("provider body must not reach durable diagnostics")

    monkeypatch.setattr(
        scheduler_service,
        "deliver_proactive_candidate",
        fail_delivery,
    )
    settings = Settings(
        scheduler_max_retries=1,
        scheduler_retry_base_seconds=5,
    )
    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate_id)
                )
            )
        ).scalar_one()
        job.run_at = utc_now() - timedelta(minutes=1)
        job_id = job.id
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert (
            await process_due_jobs(
                session,
                worker_id="retry-one",
                settings=settings,
            )
            == 1
        )
        await session.commit()
    async with AsyncSessionLocal() as session:
        job = await session.get(ScheduledJob, job_id)
        assert job is not None
        assert job.status == "pending"
        assert job.retry_count == 1
        assert "provider body" not in (job.last_error or "")
        job.run_at = utc_now() - timedelta(seconds=1)
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert (
            await process_due_jobs(
                session,
                worker_id="retry-two",
                settings=settings,
            )
            == 1
        )
        await session.commit()
    async with AsyncSessionLocal() as session:
        job = await session.get(ScheduledJob, job_id)
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert job is not None and candidate is not None
        assert job.status == "failed"
        assert job.last_error == "Job failed during execution."
        assert candidate.state == "failed"
        assert candidate.failure_code == "delivery_dead_lettered"


async def test_private_and_adult_turns_never_feed_proactive_candidates(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    age_gate = await client.patch(
        "/auth/me",
        json={"age_gate_confirmed": True},
        headers=headers,
    )
    assert age_gate.status_code == 200
    character = (await client.get("/characters", headers=headers)).json()[0]
    adult_ready = await client.patch(
        f"/characters/{character['id']}",
        json={"explicit_age": 29, "adult_mode_allowed": True},
        headers=headers,
    )
    assert adult_ready.status_code == 200

    adult_conversation = (
        await client.post(
            "/conversations",
            json={"character_id": character["id"]},
            headers=headers,
        )
    ).json()
    adult_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": adult_conversation["id"],
            "content": "Keep this turn isolated from ordinary continuity.",
            "content_mode": "adult",
        },
        headers=headers,
    )
    assert adult_chat.status_code == 200

    private_conversation = (
        await client.post(
            "/conversations",
            json={"character_id": character["id"], "privacy_mode": "private"},
            headers=headers,
        )
    ).json()
    private_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": private_conversation["id"],
            "content": "This is a private turn.",
            "privacy_mode": "private",
        },
        headers=headers,
    )
    assert private_chat.status_code == 200

    async with AsyncSessionLocal() as session:
        candidates = list(
            (
                await session.execute(
                    select(ProactiveCandidate).where(
                        ProactiveCandidate.conversation_id.in_(
                            (
                                uuid.UUID(adult_conversation["id"]),
                                uuid.UUID(private_conversation["id"]),
                            )
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
    assert candidates == []


async def test_adult_return_cancels_pending_without_creating_return_context(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation, candidate_id = await _scheduled_follow_up(client, headers)
    assert (
        await client.patch(
            "/auth/me",
            json={"age_gate_confirmed": True},
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/characters/{conversation['character_id']}",
            json={"explicit_age": 29, "adult_mode_allowed": True},
            headers=headers,
        )
    ).status_code == 200

    adult_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation["id"],
            "content": "Keep this adult-mode return isolated from ordinary continuity.",
            "content_mode": "adult",
        },
        headers=headers,
    )
    assert adult_chat.status_code == 200

    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        assert candidate.state == "cancelled"
        assert candidate.failure_code == "ineligible_user_return"
        return_count = (
            await session.execute(
                select(ProactiveCandidate).where(
                    ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"]),
                    ProactiveCandidate.candidate_type == "return",
                )
            )
        ).scalars()
        assert list(return_count) == []


async def test_sensitive_anchor_requires_an_explicit_user_reminder(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    automatic_conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    automatic_thread = await client.post(
        f"/characters/{automatic_conversation['character_id']}/threads",
        json={
            "conversation_id": automatic_conversation["id"],
            "thread_kind": "follow_up",
            "content": "Please follow up later about my therapy appointment.",
            "salience": 0.9,
        },
        headers=headers,
    )
    assert automatic_thread.status_code == 201
    assert (
        await client.post(
            "/chat/messages",
            json={
                "conversation_id": automatic_conversation["id"],
                "content": "I am leaving this topic here for now.",
            },
            headers=headers,
        )
    ).status_code == 200

    reminder_conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    reminder_thread = await client.post(
        f"/characters/{reminder_conversation['character_id']}/threads",
        json={
            "conversation_id": reminder_conversation["id"],
            "thread_kind": "follow_up",
            "content": "Remind me tomorrow to take my prescription medication.",
            "salience": 0.9,
        },
        headers=headers,
    )
    assert reminder_thread.status_code == 201
    assert (
        await client.post(
            "/chat/messages",
            json={
                "conversation_id": reminder_conversation["id"],
                "content": "That explicit reminder is all I need.",
            },
            headers=headers,
        )
    ).status_code == 200

    async with AsyncSessionLocal() as session:
        candidates = list(
            (
                await session.execute(
                    select(ProactiveCandidate).where(
                        ProactiveCandidate.conversation_id.in_(
                            (
                                uuid.UUID(automatic_conversation["id"]),
                                uuid.UUID(reminder_conversation["id"]),
                            )
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        automatic = next(
            item
            for item in candidates
            if item.conversation_id == uuid.UUID(automatic_conversation["id"])
            and item.candidate_type == "follow_up"
        )
        reminder = next(
            item
            for item in candidates
            if item.conversation_id == uuid.UUID(reminder_conversation["id"])
            and item.candidate_type == "reminder"
        )
        assert automatic.sensitivity == "sensitive"
        assert reminder.sensitivity == "sensitive"
        assert reminder.notification_preview == "New companion note"
        character = await session.get(Character, reminder.character_id)
        assert character is not None
        profile = dict(character.boundaries_json)
        preferences = dict(profile["proactive_preferences"])
        preferences["quiet_hours_start"] = "00:00"
        preferences["quiet_hours_end"] = "00:00"
        character.boundaries_json = {
            **profile,
            "proactive_preferences": preferences,
        }
        for candidate in (automatic, reminder):
            candidate.scheduled_for = utc_now() - timedelta(minutes=1)
            candidate.expires_at = utc_now() + timedelta(days=1)
            job = (
                await session.execute(
                    select(ScheduledJob).where(
                        ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                    )
                )
            ).scalar_one()
            job.run_at = candidate.scheduled_for
        automatic_id = automatic.id
        reminder_id = reminder.id
        await session.commit()

    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="sensitivity-test") == 2
        await session.commit()
    async with AsyncSessionLocal() as session:
        automatic = await session.get(ProactiveCandidate, automatic_id)
        reminder = await session.get(ProactiveCandidate, reminder_id)
        assert automatic is not None and reminder is not None
        assert automatic.state == "cancelled"
        assert automatic.failure_code == "sensitive_source_suppressed"
        assert reminder.state == "delivered"


async def _scheduled_follow_up(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    content: str = "Please follow up about my reading plan next time.",
) -> tuple[dict, uuid.UUID]:
    conversation = (await client.post("/conversations", json={}, headers=headers)).json()
    thread = await client.post(
        f"/characters/{conversation['character_id']}/threads",
        json={
            "conversation_id": conversation["id"],
            "thread_kind": "follow_up",
            "content": content,
            "salience": 0.9,
        },
        headers=headers,
    )
    assert thread.status_code == 201
    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation["id"], "content": "I will return later."},
        headers=headers,
    )
    assert chat.status_code == 200
    async with AsyncSessionLocal() as session:
        candidate = (
            await session.execute(
                select(ProactiveCandidate).where(
                    ProactiveCandidate.conversation_id == uuid.UUID(conversation["id"]),
                    ProactiveCandidate.candidate_type == "follow_up",
                )
            )
        ).scalar_one()
        return conversation, candidate.id


async def _delivered_follow_up(
    client: AsyncClient,
    headers: dict[str, str],
) -> tuple[uuid.UUID, dict]:
    conversation, candidate_id = await _scheduled_follow_up(client, headers)
    async with AsyncSessionLocal() as session:
        candidate = await session.get(ProactiveCandidate, candidate_id)
        assert candidate is not None
        candidate.expires_at = utc_now() + timedelta(days=1)
        candidate.scheduled_for = utc_now() - timedelta(minutes=1)
        character = await session.get(Character, candidate.character_id)
        assert character is not None
        profile = dict(character.boundaries_json)
        preferences = dict(profile["proactive_preferences"])
        preferences["quiet_hours_start"] = "00:00"
        preferences["quiet_hours_end"] = "00:00"
        character.boundaries_json = {
            **profile,
            "proactive_preferences": preferences,
        }
        job = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.payload_json["candidate_id"].as_string() == str(candidate.id)
                )
            )
        ).scalar_one()
        job.run_at = candidate.scheduled_for
        await session.commit()
    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="inbox-test") == 1
        await session.commit()
    return candidate_id, conversation
