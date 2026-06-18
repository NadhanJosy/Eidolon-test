from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from alembic import command

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://eidolon:eidolon_dev_password@localhost:5432/eidolon",
)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("JWT_SECRET", "test-secret-for-eidolon-tests-32-bytes")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncIterator[None]:
    await asyncio.to_thread(run_migrations)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database(prepare_database: None) -> AsyncIterator[None]:
    await truncate_tables()
    yield
    await truncate_tables()


async def truncate_tables() -> None:
    async with AsyncSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


def run_migrations() -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client
