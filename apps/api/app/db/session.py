from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings


def database_engine_options(settings: Settings) -> dict[str, Any]:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if settings.app_env == "testing":
        options["poolclass"] = NullPool
        return options
    options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        pool_recycle=settings.database_pool_recycle_seconds,
        pool_use_lifo=True,
    )
    return options


settings = get_settings()
engine = create_async_engine(settings.database_url, **database_engine_options(settings))
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
