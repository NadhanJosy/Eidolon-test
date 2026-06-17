from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, characters, chat, conversations, debug, export, health, journal, memory
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(characters.router)
    app.include_router(conversations.router)
    app.include_router(chat.router)
    app.include_router(memory.router)
    app.include_router(journal.router)
    app.include_router(debug.router)
    app.include_router(export.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "The backend hit an internal error."},
        )

    return app


app = create_app()
