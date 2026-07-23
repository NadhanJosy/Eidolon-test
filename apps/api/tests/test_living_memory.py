from __future__ import annotations

import uuid
from datetime import timedelta

from helpers import auth_headers, register_user
from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import MemoryEvidence, MemoryItem, ScheduledJob, utc_now
from app.services.jobs import create_job
from app.services.memory import (
    analyze_memory_candidate,
    create_memory,
    maintain_memories,
)
from app.services.scheduler import process_due_jobs


def test_automatic_memory_honors_opt_out_and_sensitive_content() -> None:
    opted_out = analyze_memory_candidate(
        "Do not remember this: my favorite place is the old observatory."
    )
    sensitive = analyze_memory_candidate(
        "Please remember that my email is private.person@example.com."
    )

    assert opted_out.accepted is False
    assert opted_out.reason == "user_opted_out"
    assert sensitive.accepted is False
    assert sensitive.reason == "sensitive_without_explicit_opt_in"
    assert sensitive.sensitivity == "sensitive"


async def test_reinforcement_history_entities_timeline_and_manual_sensitive_opt_in(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]

    first = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "person",
            "content": "My friend Maya runs the neighborhood book club.",
            "importance": 0.7,
            "confidence": 0.9,
        },
        headers=headers,
    )
    repeated = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "person",
            "content": "My friend Maya runs the neighborhood book club.",
            "importance": 0.72,
            "confidence": 0.9,
        },
        headers=headers,
    )
    assert first.status_code == 201
    assert repeated.status_code == 201
    assert repeated.json()["id"] == first.json()["id"]
    assert repeated.json()["reinforcement_count"] == 2
    assert repeated.json()["last_reinforced_at"] is not None

    history = await client.get(
        f"/characters/{character_id}/memories/{first.json()['id']}/history",
        headers=headers,
    )
    assert history.status_code == 200
    assert [item["action"] for item in reversed(history.json())] == ["created", "reinforced"]
    assert all("embedding" not in item["snapshot_json"] for item in history.json())

    entities = await client.get(
        f"/characters/{character_id}/memories/entities",
        headers=headers,
    )
    assert entities.status_code == 200
    maya = next(item for item in entities.json() if item["name"] == "Maya")
    assert maya["entity_type"] == "person"
    assert maya["memory_count"] == 1
    assert maya["mention_count"] == 2

    timeline = await client.get(
        f"/characters/{character_id}/memories/timeline?entity_id={maya['id']}",
        headers=headers,
    )
    assert timeline.status_code == 200
    assert [item["id"] for item in timeline.json()] == [first.json()["id"]]

    manual_sensitive = await client.post(
        f"/characters/{character_id}/memories",
        json={
            "memory_type": "user_fact",
            "content": "My email is private.person@example.com.",
            "importance": 1.0,
            "confidence": 1.0,
            "retention_tier": "core",
            "pinned": True,
        },
        headers=headers,
    )
    assert manual_sensitive.status_code == 201
    assert manual_sensitive.json()["sensitivity"] == "sensitive"
    assert manual_sensitive.json()["retention_tier"] == "core"
    assert manual_sensitive.json()["pinned"] is True

    unrelated = await client.get(
        f"/characters/{character_id}/memories/search",
        params={"q": "I got an email about weekend weather."},
        headers=headers,
    )
    assert manual_sensitive.json()["id"] not in {item["id"] for item in unrelated.json()}
    direct = await client.get(
        f"/characters/{character_id}/memories/search?q=my%20email",
        headers=headers,
    )
    assert direct.json()[0]["id"] == manual_sensitive.json()["id"]

    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    unrelated_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "I got an email about weekend plans. Can you help me plan a quiet walk?",
        },
        headers=headers,
    )
    assert unrelated_chat.status_code == 200
    unrelated_debug = await client.get(
        f"/debug/conversation/{conversation_id}",
        headers=headers,
    )
    selected_unrelated_ids = {
        item["id"]
        for item in unrelated_debug.json()["last_assembled_context"]["context_manifest"][
            "memory_items"
        ]
    }
    assert manual_sensitive.json()["id"] not in selected_unrelated_ids

    direct_chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "What is my email address?",
        },
        headers=headers,
    )
    assert direct_chat.status_code == 200
    direct_debug = await client.get(
        f"/debug/conversation/{conversation_id}",
        headers=headers,
    )
    selected_direct_ids = {
        item["id"]
        for item in direct_debug.json()["last_assembled_context"]["context_manifest"][
            "memory_items"
        ]
    }
    assert manual_sensitive.json()["id"] in selected_direct_ids

    other_token, _ = await register_user(client, email="memory-outsider@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    assert (
        await client.get(
            f"/characters/{character_id}/memories/entities",
            headers=other_headers,
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/characters/{character_id}/memories/{first.json()['id']}/history",
            headers=other_headers,
        )
    ).status_code == 404


async def test_category_erasure_is_scoped_and_permanent(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    character_id = (await client.get("/characters", headers=headers)).json()[0]["id"]
    person = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "person", "content": "My friend Rowan grows orchids."},
        headers=headers,
    )
    moment = await client.post(
        f"/characters/{character_id}/memories",
        json={"memory_type": "event", "content": "We watched a meteor shower together."},
        headers=headers,
    )
    assert person.status_code == 201
    assert moment.status_code == 201

    cleared = await client.delete(
        f"/characters/{character_id}/memories/category/people",
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json() == {"deleted": 1}

    active = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert [item["id"] for item in active.json()] == [moment.json()["id"]]
    deleted_history = await client.get(
        f"/characters/{character_id}/memories/{person.json()['id']}/history",
        headers=headers,
    )
    assert deleted_history.status_code == 404


async def test_consolidation_decay_and_scheduled_maintenance_are_inspectable(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    user_id = uuid.UUID(character["owner_user_id"])
    character_id = uuid.UUID(character["id"])

    async with AsyncSessionLocal() as session:
        for _ in range(2):
            await create_memory(
                session,
                user_id=user_id,
                character_id=character_id,
                content="User briefly mentioned a blue notebook.",
                memory_type="event",
                importance=0.1,
                confidence=0.35,
                novelty=0.2,
                future_relevance=0.1,
                retention_tier="transient",
                claim_key="event:blue-notebook",
                merge_similar=False,
                memory_source="test",
            )
        boundary = await create_memory(
            session,
            user_id=user_id,
            character_id=character_id,
            content="Please do not use surprise nicknames.",
            memory_type="boundary",
            importance=0.8,
            confidence=0.95,
            future_relevance=0.95,
            memory_source="test",
        )
        steady = await create_memory(
            session,
            user_id=user_id,
            character_id=character_id,
            content="User prefers a quiet check-in after difficult meetings.",
            memory_type="preference",
            importance=0.7,
            confidence=0.8,
            future_relevance=0.7,
            retention_tier="normal",
            memory_source="test",
        )
        review_time = utc_now() + timedelta(days=120)
        result = await maintain_memories(
            session,
            user_id,
            character_id,
            now=review_time,
        )
        await session.commit()

        assert result.reviewed == 4
        assert result.consolidated == 1
        assert result.faded == 1
        active = list(
            (
                await session.execute(
                    select(MemoryItem).where(
                        MemoryItem.user_id == user_id,
                        MemoryItem.character_id == character_id,
                        MemoryItem.lifecycle_state == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {item.id for item in active} == {boundary.id, steady.id}
        assert boundary.retention_tier == "core"
        first_decay_score = steady.decay_score
        assert first_decay_score > 0
        repeated_review = await maintain_memories(
            session,
            user_id,
            character_id,
            now=review_time,
        )
        assert repeated_review.faded == 0
        assert steady.decay_score == first_decay_score
        evidence_actions = list(
            (
                await session.execute(
                    select(MemoryEvidence.action).where(MemoryEvidence.memory_id == boundary.id)
                )
            )
            .scalars()
            .all()
        )
        assert evidence_actions == ["created"]

        job = await create_job(
            session,
            job_type="memory_maintenance",
            run_at=utc_now(),
            user_id=user_id,
            character_id=character_id,
        )
        await session.commit()
        job_id = job.id

    async with AsyncSessionLocal() as session:
        assert await process_due_jobs(session, worker_id="living-memory-test") == 1
        await session.commit()
        stored_job = await session.get(ScheduledJob, job_id)
        assert stored_job is not None
        assert stored_job.status == "done"
        assert stored_job.payload_json["result"] == "memory_maintenance_complete"
        pending = list(
            (
                await session.execute(
                    select(ScheduledJob).where(
                        ScheduledJob.job_type == "memory_maintenance",
                        ScheduledJob.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(pending) == 1
