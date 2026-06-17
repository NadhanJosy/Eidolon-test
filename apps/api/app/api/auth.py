from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models import User
from app.schemas import AuthResponse, LoginRequest, RegisterRequest, UserOut, UserUpdate
from app.security import create_access_token, hash_password, normalize_email, verify_password
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
    await session.commit()
    await session.refresh(user)
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    result = await session.execute(select(User).where(User.email == normalize_email(payload.email)))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password did not match.")
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserOut.model_validate(user),
    )


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
async def logout() -> dict[str, str]:
    return {"status": "ok"}
