from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from math import ceil

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Address

from app.config import Settings, get_settings
from app.models import AuthThrottle, utc_now

LOGIN_EMAIL_SCOPE = "login-email"
LOGIN_CLIENT_SCOPE = "login-client"
REGISTRATION_CLIENT_SCOPE = "registration-client"
UNKNOWN_CLIENT = "unavailable"


@dataclass(frozen=True)
class AuthThrottleContext:
    fingerprints: tuple[str, ...]


async def login_throttle_context(
    session: AsyncSession,
    email: str,
    client: Address | None,
    *,
    settings: Settings | None = None,
) -> AuthThrottleContext:
    runtime_settings = settings or get_settings()
    return await auth_throttle_context(
        session,
        (
            (LOGIN_EMAIL_SCOPE, email),
            (LOGIN_CLIENT_SCOPE, _client_host(client)),
        ),
        secret=runtime_settings.jwt_signing_key,
    )


async def registration_throttle_context(
    session: AsyncSession,
    client: Address | None,
    *,
    settings: Settings | None = None,
) -> AuthThrottleContext:
    runtime_settings = settings or get_settings()
    return await auth_throttle_context(
        session,
        ((REGISTRATION_CLIENT_SCOPE, _client_host(client)),),
        secret=runtime_settings.jwt_signing_key,
    )


async def auth_throttle_context(
    session: AsyncSession,
    scoped_values: tuple[tuple[str, str], ...],
    *,
    secret: str,
) -> AuthThrottleContext:
    fingerprints = tuple(
        sorted({throttle_fingerprint(scope, value, secret) for scope, value in scoped_values})
    )
    if not fingerprints:
        raise ValueError("At least one auth throttle scope is required.")
    for lock_key in sorted({_advisory_lock_key(value) for value in fingerprints}):
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
    return AuthThrottleContext(fingerprints=fingerprints)


async def check_login_throttle(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    now: datetime | None = None,
) -> int | None:
    return await check_auth_throttle(session, context, now=now)


async def check_registration_throttle(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    now: datetime | None = None,
) -> int | None:
    return await check_auth_throttle(session, context, now=now)


async def check_auth_throttle(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    now: datetime | None = None,
) -> int | None:
    checked_at = now or utc_now()
    records = (
        await session.scalars(
            select(AuthThrottle).where(AuthThrottle.fingerprint.in_(context.fingerprints))
        )
    ).all()
    retry_seconds = [
        _retry_after_seconds(record.blocked_until, checked_at)
        for record in records
        if record.blocked_until is not None and record.blocked_until > checked_at
    ]
    return max(retry_seconds, default=None)


async def record_login_failure(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int | None:
    runtime_settings = settings or get_settings()
    return await record_auth_attempt(
        session,
        context,
        max_attempts=runtime_settings.login_max_attempts,
        window_seconds=runtime_settings.login_attempt_window_seconds,
        block_seconds=runtime_settings.login_block_seconds,
        retention_seconds=_retention_seconds(runtime_settings),
        now=now,
    )


async def record_registration_attempt(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int | None:
    runtime_settings = settings or get_settings()
    return await record_auth_attempt(
        session,
        context,
        max_attempts=runtime_settings.registration_max_attempts,
        window_seconds=runtime_settings.registration_attempt_window_seconds,
        block_seconds=runtime_settings.registration_block_seconds,
        retention_seconds=_retention_seconds(runtime_settings),
        now=now,
    )


async def record_auth_attempt(
    session: AsyncSession,
    context: AuthThrottleContext,
    *,
    max_attempts: int,
    window_seconds: int,
    block_seconds: int,
    retention_seconds: int,
    now: datetime | None = None,
) -> int | None:
    attempted_at = now or utc_now()
    window = timedelta(seconds=window_seconds)
    blocked_until: list[datetime] = []

    for fingerprint in context.fingerprints:
        record = await session.get(AuthThrottle, fingerprint)
        if record is None:
            record = AuthThrottle(
                fingerprint=fingerprint,
                failed_attempts=1,
                window_started_at=attempted_at,
                blocked_until=None,
                last_attempt_at=attempted_at,
            )
            session.add(record)
        elif attempted_at - record.window_started_at >= window:
            record.failed_attempts = 1
            record.window_started_at = attempted_at
            record.blocked_until = None
            record.last_attempt_at = attempted_at
        else:
            record.failed_attempts += 1
            record.last_attempt_at = attempted_at

        if record.failed_attempts >= max_attempts:
            record.blocked_until = attempted_at + timedelta(seconds=block_seconds)
            blocked_until.append(record.blocked_until)

    retention = timedelta(seconds=retention_seconds)
    await session.execute(
        delete(AuthThrottle).where(AuthThrottle.last_attempt_at < attempted_at - retention)
    )
    if not blocked_until:
        return None
    return max(_retry_after_seconds(value, attempted_at) for value in blocked_until)


async def clear_login_failures(
    session: AsyncSession,
    context: AuthThrottleContext,
) -> None:
    await session.execute(
        delete(AuthThrottle).where(AuthThrottle.fingerprint.in_(context.fingerprints))
    )


def throttle_fingerprint(scope: str, value: str, secret: str) -> str:
    payload = f"{scope}\0{value}".encode()
    return hmac_new(secret.encode(), payload, sha256).hexdigest()


def _client_host(client: Address | None) -> str:
    return client.host if client is not None and client.host else UNKNOWN_CLIENT


def _retention_seconds(settings: Settings) -> int:
    return (
        max(
            settings.login_attempt_window_seconds,
            settings.login_block_seconds,
            settings.registration_attempt_window_seconds,
            settings.registration_block_seconds,
        )
        * 4
    )


def _advisory_lock_key(fingerprint: str) -> int:
    return int.from_bytes(bytes.fromhex(fingerprint)[:8], byteorder="big", signed=True)


def _retry_after_seconds(blocked_until: datetime, now: datetime) -> int:
    return max(1, ceil((blocked_until - now).total_seconds()))
