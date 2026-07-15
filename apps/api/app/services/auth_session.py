from __future__ import annotations

from fastapi import HTTPException, Request, Response

from app.config import Settings, get_settings

REFRESH_COOKIE_NAME = "eidolon_refresh"
REFRESH_COOKIE_PATH = "/auth"


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
    *,
    settings: Settings | None = None,
) -> None:
    runtime_settings = settings or get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=runtime_settings.refresh_cookie_max_age_seconds,
        path=REFRESH_COOKIE_PATH,
        secure=runtime_settings.refresh_cookie_secure,
        httponly=True,
        samesite=runtime_settings.refresh_cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )


def request_refresh_token(
    request: Request,
    legacy_body_token: str | None = None,
    *,
    settings: Settings | None = None,
) -> str | None:
    validate_request_origin(request, settings=settings)
    cookie_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if _valid_token_shape(cookie_token):
        return cookie_token
    return legacy_body_token if _valid_token_shape(legacy_body_token) else None


def validate_request_origin(
    request: Request,
    *,
    settings: Settings | None = None,
) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        return
    normalized_origin = origin.strip().rstrip("/")
    runtime_settings = settings or get_settings()
    if normalized_origin not in runtime_settings.allowed_origins:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


def _valid_token_shape(value: str | None) -> bool:
    return isinstance(value, str) and 32 <= len(value) <= 512
