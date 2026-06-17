from __future__ import annotations

from httpx import AsyncClient


async def test_health_exact(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "eidolon-api"}


async def test_health_db(client: AsyncClient) -> None:
    response = await client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_llm_mock(client: AsyncClient) -> None:
    response = await client.get("/health/llm")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
