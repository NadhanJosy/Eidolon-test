from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.llm.factory import get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "eidolon-api"}


@router.get("/ready", response_class=JSONResponse)
async def ready(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unavailable"},
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        content={"status": "ready", "database": "ok"},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/health/db")
async def health_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/health/llm")
async def health_llm() -> dict[str, str]:
    provider = get_llm_provider()
    return await provider.health()
