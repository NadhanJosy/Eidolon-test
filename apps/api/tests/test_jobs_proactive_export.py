from __future__ import annotations

import uuid
from datetime import timedelta

from helpers import auth_headers, register_user
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models import Character, Conversation, MemoryItem, Message, ScheduledJob, User, utc_now
from app.services.jobs import claim_due_jobs, create_job, mark_job_done
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
        await mark_job_done(session, jobs[0])
        await session.commit()


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
    assert first.json()["metadata_json"]["proactive"] is True
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
        assert stored_messages[0].metadata_json["proactive_label"] == "thinking-of-you note"
        assert "thinking about our conversation" in stored_messages[0].content


async def test_scheduler_proactive_variants_respect_cooldown(client: AsyncClient) -> None:
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
        assert first_job.payload_json["result"] == "message_created"
        assert first_job.payload_json["proactive_type"] == "proactive_morning_check"
        assert second_job.payload_json["result"] == "skipped_by_cooldown_or_state"

        proactive_messages = await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(conversation["id"]),
                Message.role == "assistant",
                Message.metadata_json["proactive"].as_boolean().is_(True),
            )
        )
        stored_messages = list(proactive_messages.scalars().all())
        assert len(stored_messages) == 1
        assert stored_messages[0].metadata_json["proactive_label"] == "morning note"


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

        memories = await session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == uuid.UUID(conversation["user_id"]),
                MemoryItem.character_id == uuid.UUID(conversation["character_id"]),
            )
        )
        stored_memories = list(memories.scalars().all())
        assert len(stored_memories) == 1
        assert "rain at night" in stored_memories[0].content


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


async def test_export_excludes_secrets(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    export = await client.get("/account/export", headers=headers)

    assert export.status_code == 200
    text = export.text
    assert "password_hash" not in text
    assert "token_hash" not in text
    assert "test-secret" not in text


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
