from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.services.chat import ensure_default_character

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
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
    response = await issue_auth_response(session, user)
    await session.commit()
    await session.refresh(user)
    return response


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    result = await session.execute(select(User).where(User.email == normalize_email(payload.email)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password did not match.")
    response = await issue_auth_response(session, user)
    await session.commit()
    return response


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    stored_token = await find_active_refresh_token(session, payload.refresh_token)
    if stored_token is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired.")

    user = await session.get(User, stored_token.user_id)
    stored_token.revoked_at = utc_now()
    if user is None:
        await session.commit()
        raise HTTPException(status_code=401, detail="Refresh token no longer matches a user.")

    response = await issue_auth_response(session, user)
    await session.commit()
    return response


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.age_gate_confirmed is not None:
        user.age_gate_confirmed = payload.age_gate_confirmed
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/logout")
async def logout(
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: LogoutRequest | None = None,
) -> dict[str, str]:
    if payload is not None and payload.refresh_token:
        stored_token = await find_refresh_token(session, payload.refresh_token)
        if stored_token is not None and stored_token.revoked_at is None:
            stored_token.revoked_at = utc_now()
            await session.commit()
    return {"status": "ok"}


async def issue_auth_response(session: AsyncSession, user: User) -> AuthResponse:
    refresh_token_value = create_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token_value),
            expires_at=utc_now() + get_settings().refresh_token_lifetime,
        )
    )
    await session.flush()
    return AuthResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token_value,
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
