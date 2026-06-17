from __future__ import annotations

from datetime import timedelta

from helpers import auth_headers
from httpx import AsyncClient

from app.db.session import AsyncSessionLocal
from app.models import utc_now
from app.services.jobs import claim_due_jobs, create_job, mark_job_done


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


async def test_export_excludes_secrets(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    export = await client.get("/account/export", headers=headers)

    assert export.status_code == 200
    text = export.text
    assert "password_hash" not in text
    assert "token_hash" not in text
    assert "test-secret" not in text
