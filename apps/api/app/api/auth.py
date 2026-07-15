from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models import RefreshToken, User, utc_now
from app.schemas import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UserOut,
    UserUpdate,
)
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.services.auth_session import (
    clear_refresh_cookie,
    request_refresh_token,
    set_refresh_cookie,
    validate_request_origin,
)
from app.services.auth_throttle import (
    check_login_throttle,
    check_registration_throttle,
    clear_login_failures,
    login_throttle_context,
    record_login_failure,
    record_registration_attempt,
    registration_throttle_context,
)
from app.services.chat import ensure_default_character

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    validate_request_origin(request)
    throttle = await registration_throttle_context(session, request.client)
    retry_after = await check_registration_throttle(session, throttle)
    if retry_after is not None:
        await session.commit()
        raise registration_throttled_error(retry_after)
    await record_registration_attempt(session, throttle)
    await session.commit()

    user = User(
        email=normalize_email(payload.email),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        age_gate_confirmed=False,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="That email is already registered.") from exc

    await ensure_default_character(session, user)
    auth_response = await issue_auth_response(session, user, response)
    await session.commit()
    await session.refresh(user)
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    validate_request_origin(request)
    email = normalize_email(payload.email)
    throttle = await login_throttle_context(session, email, request.client)
    retry_after = await check_login_throttle(session, throttle)
    if retry_after is not None:
        await session.commit()
        raise login_throttled_error(retry_after)

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, password_hash)
    if user is None or not password_matches:
        retry_after = await record_login_failure(session, throttle)
        await session.commit()
        if retry_after is not None:
            raise login_throttled_error(retry_after)
        raise HTTPException(status_code=401, detail="Email or password did not match.")
    await clear_login_failures(session, throttle)
    auth_response = await issue_auth_response(session, user, response)
    await session.commit()
    return auth_response


def login_throttled_error(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many sign-in attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def registration_throttled_error(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many account creation attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: RefreshRequest | None = None,
) -> AuthResponse:
    legacy_token = payload.refresh_token if payload is not None else None
    refresh_token_value = request_refresh_token(request, legacy_token)
    if refresh_token_value is None:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired.")

    stored_token = await find_active_refresh_token(session, refresh_token_value)
    if stored_token is None:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired.")

    user = await session.get(User, stored_token.user_id)
    stored_token.revoked_at = utc_now()
    if user is None:
        await session.commit()
        raise HTTPException(status_code=401, detail="Refresh token no longer matches a user.")

    auth_response = await issue_auth_response(session, user, response)
    await session.commit()
    return auth_response


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    if "age_gate_confirmed" in payload.model_fields_set:
        user.age_gate_confirmed = payload.age_gate_confirmed
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: LogoutRequest | None = None,
) -> dict[str, str]:
    legacy_token = payload.refresh_token if payload is not None else None
    refresh_token_value = request_refresh_token(request, legacy_token)
    if refresh_token_value is not None:
        stored_token = await find_refresh_token(session, refresh_token_value)
        if stored_token is not None and stored_token.revoked_at is None:
            stored_token.revoked_at = utc_now()
            await session.commit()
    clear_refresh_cookie(response)
    return {"status": "ok"}


async def issue_auth_response(
    session: AsyncSession,
    user: User,
    response: Response,
) -> AuthResponse:
    refresh_token_value = create_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token_value),
            expires_at=utc_now() + get_settings().refresh_token_lifetime,
        )
    )
    await session.flush()
    set_refresh_cookie(response, refresh_token_value)
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


async def find_active_refresh_token(
    session: AsyncSession,
    refresh_token_value: str,
) -> RefreshToken | None:
    token = await find_refresh_token(session, refresh_token_value)
    if token is None or token.revoked_at is not None or token.expires_at <= utc_now():
        return None
    return token


async def find_refresh_token(
    session: AsyncSession,
    refresh_token_value: str,
) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token_value)
        )
    )
    return result.scalar_one_or_none()
