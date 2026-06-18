from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from helpers import auth_headers, register_user
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models import RelationshipState, ScheduledJob
from app.services.jobs import create_job
from app.services.scheduler import process_due_jobs


async def test_memory_v2_edit_delete_dedupe_and_contradiction(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    first = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "preference",
            "content": "I like tea.",
            "importance": 0.8,
            "confidence": 0.9,
            "pinned": True,
        },
        headers=headers,
    )
    assert first.status_code == 201
    duplicate = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I like tea.", "confidence": 0.7},
        headers=headers,
    )
    assert duplicate.status_code == 201

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert len(memories.json()) == 1
    memory_id = memories.json()[0]["id"]
    assert memories.json()[0]["pinned"] is True

    edited = await client.patch(
        f"/characters/{character_id}/memories/{memory_id}",
        json={"content": "I like jasmine tea.", "importance": 0.9, "pinned": False},
        headers=headers,
    )
    assert edited.status_code == 200
    assert edited.json()["importance"] == 0.9
    assert edited.json()["pinned"] is False

    contradiction = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "preference", "content": "I don't like jasmine tea."},
        headers=headers,
    )
    assert contradiction.status_code == 201
    assert contradiction.json()["contradiction_group"] == "preference:jasmine-tea"
    assert contradiction.json()["metadata_json"]["contradicts_memory_id"] == memory_id

    removed = await client.delete(
        f"/characters/{character_id}/memories/{memory_id}",
        headers=headers,
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] == 1

    cleared = await client.delete(f"/characters/{character_id}/memories", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1


async def test_journal_relationship_and_proactive_hooks_after_chat(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Thanks. Remember that our inside joke is the midnight kettle?",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["assistant_message"]["metadata_json"]["delivery_state"]["read_state"] == (
        "delivered"
    )

    journals = await client.get(f"/characters/{character_id}/journals", headers=headers)
    assert journals.status_code == 200
    assert len(journals.json()) == 1
    assert journals.json()[0]["callbacks_json"]

    relationship = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    assert relationship.json()["metadata_json"]["timeline"]

    jobs = await client.get("/debug/jobs", headers=headers)
    assert jobs.status_code == 200
    job_types = {job["job_type"] for job in jobs.json()}
    assert "relationship_decay" in job_types
    assert "proactive_inactivity_check" in job_types
    assert "proactive_unresolved_thread_nudge" in job_types


async def test_relationship_read_applies_absence_decay(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    character_id = conversation.json()["character_id"]
    character_uuid = uuid.UUID(character_id)

    await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Thank you, I am glad we can talk.",
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        relationship.warmth = 12.0
        relationship.tension = 6.0
        relationship.attachment = 3.0
        relationship.last_interaction_at = datetime.now(UTC) - timedelta(days=5)
        await session.commit()

    response = await client.get(f"/characters/{character_id}/relationship", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["warmth"] < 12.0
    assert payload["tension"] < 6.0
    assert "absence" in payload["tags_json"]
    assert payload["metadata_json"]["timeline"][-1]["kind"] == "decay"


async def test_scheduler_processes_relationship_decay_job(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    character_id = conversation.json()["character_id"]
    user_id = conversation.json()["user_id"]
    character_uuid = uuid.UUID(character_id)
    user_uuid = uuid.UUID(user_id)

    await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation.json()["id"],
            "content": "Thank you, I appreciate this.",
        },
        headers=headers,
    )

    async with AsyncSessionLocal() as session:
        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        relationship.warmth = 10.0
        relationship.tension = 4.0
        relationship.last_interaction_at = datetime.now(UTC) - timedelta(days=4)
        await session.execute(
            delete(ScheduledJob).where(
                ScheduledJob.user_id == user_uuid,
                ScheduledJob.character_id == character_uuid,
                ScheduledJob.job_type == "relationship_decay",
            )
        )
        job = await create_job(
            session,
            job_type="relationship_decay",
            run_at=datetime.now(UTC) - timedelta(minutes=1),
            user_id=user_uuid,
            character_id=character_uuid,
            payload_json={"source": "test"},
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
        assert stored_job.payload_json["result"] == "relationship_decay_applied"
        queued_next = (
            await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.user_id == user_uuid,
                    ScheduledJob.character_id == character_uuid,
                    ScheduledJob.job_type == "relationship_decay",
                    ScheduledJob.status == "pending",
                )
            )
        ).scalar_one_or_none()
        assert queued_next is not None

        relationship = (
            await session.execute(
                select(RelationshipState).where(
                    RelationshipState.character_id == character_uuid,
                )
            )
        ).scalar_one()
        assert relationship.warmth < 10.0
        assert "absence" in relationship.tags_json


async def test_adult_status_and_access_control_are_structural(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    status = await client.get(f"/characters/{character_id}/adult-status", headers=headers)
    assert status.status_code == 200
    assert status.json()["effective_mode"] == "sfw"
    assert "User age gate is not confirmed." in status.json()["reasons"]

    token_two, _ = await register_user(
        client,
        email="second@example.com",
        password="good-password",
    )
    other_headers = {"Authorization": f"Bearer {token_two}"}
    blocked = await client.get(f"/characters/{character_id}", headers=other_headers)
    assert blocked.status_code == 404


async def test_conversation_clear_and_reroll(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assistant_id = chat.json()["assistant_message"]["id"]
    jobs_before_clear = await client.get("/debug/jobs", headers=headers)
    assert jobs_before_clear.status_code == 200
    assert jobs_before_clear.json()

    reroll = await client.post(
        "/chat/reroll",
        json={"conversation_id": conversation_id, "assistant_message_id": assistant_id},
        headers=headers,
    )
    assert reroll.status_code == 200
    assert reroll.json()["metadata_json"]["reroll_of"] == assistant_id

    clear = await client.delete(f"/conversations/{conversation_id}/messages", headers=headers)
    assert clear.status_code == 200
    assert clear.json()["deleted"] == 3

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.json() == []

    jobs_after_clear = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after_clear.json(), conversation_id) == 0


async def test_conversation_title_can_be_updated(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={"title": "Old title"}, headers=headers)
    conversation_id = conversation.json()["id"]

    updated = await client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Quiet evening"},
        headers=headers,
    )

    assert updated.status_code == 200
    assert updated.json()["title"] == "Quiet evening"


async def test_conversation_delete_removes_queued_jobs(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assert chat.status_code == 200

    jobs_before_delete = await client.get("/debug/jobs", headers=headers)
    assert jobs_before_delete.json()

    deleted = await client.delete(f"/conversations/{conversation_id}", headers=headers)
    assert deleted.status_code == 200

    jobs_after_delete = await client.get("/debug/jobs", headers=headers)
    assert _conversation_job_count(jobs_after_delete.json(), conversation_id) == 0


def _conversation_job_count(jobs: list[dict], conversation_id: str) -> int:
    return sum(
        1
        for job in jobs
        if (job.get("payload_json") or {}).get("conversation_id") == conversation_id
    )
