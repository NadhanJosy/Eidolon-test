from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient
from pytest import MonkeyPatch

from app.config import Settings
from app.main import lifespan


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
    assert response.json() == {
        "status": "ok",
        "provider": "mock",
        "model": "deterministic-companion-mock",
        "configuration": "configured",
        "readiness": "development",
    }


async def test_lifespan_owns_enabled_scheduler(monkeypatch: MonkeyPatch) -> None:
    settings = Settings(
        enable_scheduler=True,
        scheduler_interval_seconds=30,
        scheduler_job_limit=5,
    )
    events: list[str] = []

    class FakeScheduler:
        running = True

        def shutdown(self, *, wait: bool) -> None:
            assert wait is False
            events.append("stopped")

    fake_scheduler = FakeScheduler()

    def start_scheduler(*, settings: Settings) -> FakeScheduler:
        assert settings.enable_scheduler is True
        events.append("started")
        return fake_scheduler

    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.start_background_scheduler", start_scheduler)
    test_app = FastAPI()

    async with lifespan(test_app):
        assert events == ["started"]
        assert test_app.state.scheduler_enabled is True
        assert test_app.state.scheduler is fake_scheduler

    assert events == ["started", "stopped"]
    assert test_app.state.scheduler is None
