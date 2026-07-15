from __future__ import annotations

import asyncio
from datetime import timedelta

from helpers import auth_headers, register_user
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select, update

from app import security as security_module
from app.api import auth as auth_api
from app.config import Settings, get_settings
from app.db.session import AsyncSessionLocal
from app.models import AuthThrottle, User, utc_now
from app.security import DUMMY_PASSWORD_HASH, verify_password
from app.services.auth_session import REFRESH_COOKIE_NAME
from app.services.auth_throttle import (
    LOGIN_CLIENT_SCOPE,
    LOGIN_EMAIL_SCOPE,
    REGISTRATION_CLIENT_SCOPE,
    throttle_fingerprint,
)


async def test_register_login_me_and_default_character(client: AsyncClient) -> None:
    headers = await auth_headers(client)

    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    characters = await client.get("/characters", headers=headers)
    assert characters.status_code == 200
    assert len(characters.json()) == 1
    default_character = characters.json()[0]
    assert default_character["name"] == "Eidolon"
    assert default_character["boundaries_json"]["greeting"].startswith("You made it back")
    assert "opt-in" in default_character["boundaries_json"]["consent_style"]
    assert default_character["boundaries_json"]["memory_preferences"] == {
        "remember_preferences": True,
        "remember_emotional_notes": True,
        "private_mode_default": False,
        "adult_memory_storage": False,
    }

    login = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "good-password"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]
    assert "refresh_token" not in login.json()
    set_cookie = login.headers["set-cookie"]
    assert f"{REFRESH_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


async def test_account_profile_update_normalizes_clears_and_rejects_empty_changes(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)

    renamed = await client.patch(
        "/auth/me",
        json={"display_name": "  Private   Name  "},
        headers=headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "Private Name"
    assert renamed.json()["created_at"]

    cleared = await client.patch(
        "/auth/me",
        json={"display_name": "   "},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["display_name"] is None

    confirmed = await client.patch(
        "/auth/me",
        json={"age_gate_confirmed": True},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["age_gate_confirmed"] is True

    empty = await client.patch("/auth/me", json={}, headers=headers)
    assert empty.status_code == 422

    null_age_gate = await client.patch(
        "/auth/me",
        json={"age_gate_confirmed": None},
        headers=headers,
    )
    assert null_age_gate.status_code == 422

    canonical = await client.get("/auth/me", headers=headers)
    assert canonical.status_code == 200
    assert canonical.json()["display_name"] is None
    assert canonical.json()["age_gate_confirmed"] is True


async def test_character_profile_update_rejects_empty_and_required_null_fields(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]
    character_id = character["id"]

    empty = await client.patch(f"/characters/{character_id}", json={}, headers=headers)
    assert empty.status_code == 422

    for field_name in (
        "name",
        "boundaries_json",
        "adult_mode_allowed",
        "content_intensity",
    ):
        rejected = await client.patch(
            f"/characters/{character_id}",
            json={field_name: None},
            headers=headers,
        )
        assert rejected.status_code == 422, field_name

    control_name = await client.patch(
        f"/characters/{character_id}",
        json={"name": "Trusted\u202eName"},
        headers=headers,
    )
    assert control_name.status_code == 422

    cleared = await client.patch(
        f"/characters/{character_id}",
        json={
            "description": None,
            "personality_core": None,
            "speech_style": None,
            "explicit_age": None,
        },
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["id"] == character_id
    assert cleared.json()["owner_user_id"] == character["owner_user_id"]
    assert cleared.json()["name"] == character["name"]
    assert cleared.json()["description"] is None
    assert cleared.json()["personality_core"] is None
    assert cleared.json()["speech_style"] is None
    assert cleared.json()["explicit_age"] is None


async def test_conversation_titles_normalize_and_updates_reject_empty_or_null_fields(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    character = (await client.get("/characters", headers=headers)).json()[0]

    created = await client.post(
        "/conversations",
        json={
            "character_id": character["id"],
            "title": "  A   Quiet   Room  ",
            "privacy_mode": "private",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["user_id"] == character["owner_user_id"]
    assert conversation["character_id"] == character["id"]
    assert conversation["title"] == "A Quiet Room"
    assert conversation["metadata_json"]["privacy_mode"] == "private"
    assert conversation["metadata_json"]["scenario_mode"] == "default"
    assert conversation["last_message_at"] is None
    assert conversation["unread_count"] == 0
    assert conversation["created_at"]
    assert conversation["updated_at"]

    conversation_id = conversation["id"]
    empty = await client.patch(f"/conversations/{conversation_id}", json={}, headers=headers)
    assert empty.status_code == 422

    for field_name in ("privacy_mode", "scenario"):
        rejected = await client.patch(
            f"/conversations/{conversation_id}",
            json={field_name: None},
            headers=headers,
        )
        assert rejected.status_code == 422, field_name

    control_title = await client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "Trusted\u202eRoom"},
        headers=headers,
    )
    assert control_title.status_code == 422

    control_create = await client.post(
        "/conversations",
        json={"character_id": character["id"], "title": "New\u200bRoom"},
        headers=headers,
    )
    assert control_create.status_code == 422

    cleared = await client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "   "},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["title"] is None
    assert cleared.json()["metadata_json"]["privacy_mode"] == "private"


async def test_registration_normalizes_identity_and_rejects_malformed_input(
    client: AsyncClient,
) -> None:
    registered = await client.post(
        "/auth/register",
        json={
            "email": "  Mixed.Case+tag@Example.COM  ",
            "password": "a secure passphrase",
            "display_name": "  Ada   Lovelace  ",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["user"]["email"] == "mixed.case+tag@example.com"
    assert registered.json()["user"]["display_name"] == "Ada Lovelace"

    canonical_login = await client.post(
        "/auth/login",
        json={
            "email": " MIXED.CASE+TAG@EXAMPLE.COM ",
            "password": "a secure passphrase",
        },
    )
    assert canonical_login.status_code == 200

    duplicate = await client.post(
        "/auth/register",
        json={
            "email": "mixed.case+tag@example.com",
            "password": "another passphrase",
            "display_name": "Duplicate",
        },
    )
    assert duplicate.status_code == 409

    blank_name = await client.post(
        "/auth/register",
        json={
            "email": "blank-name@example.com",
            "password": "another passphrase",
            "display_name": "   ",
        },
    )
    assert blank_name.status_code == 201
    assert blank_name.json()["user"]["display_name"] is None

    invalid_payloads = [
        {"email": "plain-address", "password": "a secure passphrase"},
        {"email": "user@example", "password": "a secure passphrase"},
        {"email": "user..name@example.com", "password": "a secure passphrase"},
        {"email": "user@-example.com", "password": "a secure passphrase"},
        {"email": "user@example..com", "password": "a secure passphrase"},
        {"email": "user@exam_ple.com", "password": "a secure passphrase"},
        {"email": "user@example.com", "password": "short-pass"},
        {"email": "user@example.com", "password": "            "},
        {
            "email": "user@example.com",
            "password": "a secure passphrase",
            "display_name": "Hidden\u200dJoiner",
        },
    ]
    for payload in invalid_payloads:
        rejected = await client.post("/auth/register", json=payload)
        assert rejected.status_code == 422, (payload, rejected.text)


async def test_registration_throttle_bounds_hashing_and_survives_rejected_requests(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = get_settings()
    hashed_passwords: list[str] = []

    def record_hash(password: str) -> str:
        hashed_passwords.append(password)
        return "test-registration-password-hash"

    monkeypatch.setattr(auth_api, "hash_password", record_hash)
    first = await client.post(
        "/auth/register",
        json={
            "email": "bounded-0@example.com",
            "password": "a bounded passphrase",
            "display_name": "Bounded Zero",
        },
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/auth/register",
        json={
            "email": "bounded-0@example.com",
            "password": "a bounded passphrase",
            "display_name": "Duplicate",
        },
    )
    assert duplicate.status_code == 409

    invalid = await client.post(
        "/auth/register",
        json={
            "email": "invalid@example.com",
            "password": "short",
            "display_name": "Invalid",
        },
    )
    assert invalid.status_code == 422

    rejected_origin = await client.post(
        "/auth/register",
        json={
            "email": "origin-rejected@example.com",
            "password": "a bounded passphrase",
            "display_name": "Rejected Origin",
        },
        headers={"Origin": "https://untrusted.example"},
    )
    assert rejected_origin.status_code == 403

    for attempt in range(1, settings.registration_max_attempts - 1):
        accepted = await client.post(
            "/auth/register",
            json={
                "email": f"bounded-{attempt}@example.com",
                "password": "a bounded passphrase",
                "display_name": f"Bounded {attempt}",
            },
        )
        assert accepted.status_code == 201, accepted.text

    blocked = await client.post(
        "/auth/register",
        json={
            "email": "bounded-blocked@example.com",
            "password": "a bounded passphrase",
            "display_name": "Blocked",
        },
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many account creation attempts. Try again later."
    assert int(blocked.headers["retry-after"]) in range(
        settings.registration_block_seconds - 1,
        settings.registration_block_seconds + 1,
    )
    assert len(hashed_passwords) == settings.registration_max_attempts

    expected_fingerprint = throttle_fingerprint(
        REGISTRATION_CLIENT_SCOPE,
        "127.0.0.1",
        settings.jwt_signing_key,
    )
    async with AsyncSessionLocal() as session:
        records = (await session.scalars(select(AuthThrottle))).all()
        persisted_users = (await session.scalars(select(User))).all()
    assert len(records) == 1
    assert records[0].fingerprint == expected_fingerprint
    assert records[0].failed_attempts == settings.registration_max_attempts
    assert records[0].blocked_until is not None
    assert len(persisted_users) == settings.registration_max_attempts - 1
    assert "127.0.0.1" not in records[0].fingerprint
    assert "example.com" not in records[0].fingerprint


async def test_registration_throttle_recovers_after_expired_window(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(auth_api, "hash_password", lambda _password: "test-password-hash")

    for attempt in range(settings.registration_max_attempts):
        accepted = await client.post(
            "/auth/register",
            json={
                "email": f"expiry-{attempt}@example.com",
                "password": "an expiry passphrase",
                "display_name": f"Expiry {attempt}",
            },
        )
        assert accepted.status_code == 201

    blocked = await client.post(
        "/auth/register",
        json={
            "email": "expiry-blocked@example.com",
            "password": "an expiry passphrase",
            "display_name": "Blocked",
        },
    )
    assert blocked.status_code == 429

    expired_at = utc_now() - timedelta(seconds=1)
    stale_window = utc_now() - timedelta(seconds=settings.registration_attempt_window_seconds + 1)
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AuthThrottle).values(
                blocked_until=expired_at,
                window_started_at=stale_window,
                last_attempt_at=expired_at,
            )
        )
        await session.commit()

    recovered = await client.post(
        "/auth/register",
        json={
            "email": "expiry-recovered@example.com",
            "password": "an expiry passphrase",
            "display_name": "Recovered",
        },
    )
    assert recovered.status_code == 201
    async with AsyncSessionLocal() as session:
        record = (await session.scalars(select(AuthThrottle))).one()
    assert record.failed_attempts == 1
    assert record.blocked_until is None


async def test_registration_throttle_serializes_parallel_account_creation(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = get_settings()
    hash_count = 0

    def record_hash(_password: str) -> str:
        nonlocal hash_count
        hash_count += 1
        return "parallel-registration-password-hash"

    monkeypatch.setattr(auth_api, "hash_password", record_hash)
    request_count = settings.registration_max_attempts + 3
    responses = await asyncio.gather(
        *(
            client.post(
                "/auth/register",
                json={
                    "email": f"parallel-registration-{attempt}@example.com",
                    "password": "a parallel passphrase",
                    "display_name": f"Parallel {attempt}",
                },
            )
            for attempt in range(request_count)
        )
    )
    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == settings.registration_max_attempts
    assert statuses.count(429) == 3
    assert hash_count == settings.registration_max_attempts


async def test_login_keeps_unknown_and_corrupt_accounts_on_safe_failure_path(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    observed_hashes: list[str] = []

    def record_verification(password: str, password_hash: str) -> bool:
        assert password == "unknown passphrase"
        observed_hashes.append(password_hash)
        return False

    monkeypatch.setattr(auth_api, "verify_password", record_verification)
    unknown = await client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "unknown passphrase"},
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "Email or password did not match."
    assert observed_hashes == [DUMMY_PASSWORD_HASH]

    monkeypatch.undo()
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                email="corrupt@example.com",
                password_hash="not-an-argon2-hash",
                display_name="Corrupt",
                age_gate_confirmed=False,
            )
        )
        await session.commit()

    corrupt = await client.post(
        "/auth/login",
        json={"email": "corrupt@example.com", "password": "unknown passphrase"},
    )
    assert corrupt.status_code == 401
    assert corrupt.json()["detail"] == "Email or password did not match."
    assert verify_password("unknown passphrase", "not-an-argon2-hash") is False


async def test_login_throttle_blocks_known_account_and_expires(
    client: AsyncClient,
) -> None:
    await register_user(
        client,
        email="limited@example.com",
        password="correct passphrase",
    )
    settings = get_settings()

    for _ in range(settings.login_max_attempts - 1):
        rejected = await client.post(
            "/auth/login",
            json={"email": "limited@example.com", "password": "wrong passphrase"},
        )
        assert rejected.status_code == 401
        assert rejected.json()["detail"] == "Email or password did not match."

    blocked = await client.post(
        "/auth/login",
        json={"email": "limited@example.com", "password": "wrong passphrase"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many sign-in attempts. Try again later."
    assert int(blocked.headers["retry-after"]) in range(
        settings.login_block_seconds - 1,
        settings.login_block_seconds + 1,
    )

    correct_but_blocked = await client.post(
        "/auth/login",
        json={"email": "limited@example.com", "password": "correct passphrase"},
    )
    assert correct_but_blocked.status_code == 429

    expired_at = utc_now() - timedelta(seconds=1)
    stale_window = utc_now() - timedelta(seconds=settings.login_attempt_window_seconds + 1)
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AuthThrottle).values(
                blocked_until=expired_at,
                window_started_at=stale_window,
                last_attempt_at=expired_at,
            )
        )
        await session.commit()

    recovered = await client.post(
        "/auth/login",
        json={"email": "limited@example.com", "password": "correct passphrase"},
    )
    assert recovered.status_code == 200
    async with AsyncSessionLocal() as session:
        records = (await session.scalars(select(AuthThrottle))).all()
    remaining_fingerprints = {record.fingerprint for record in records}
    assert remaining_fingerprints == {
        throttle_fingerprint(
            REGISTRATION_CLIENT_SCOPE,
            "127.0.0.1",
            settings.jwt_signing_key,
        )
    }
    assert (
        throttle_fingerprint(
            LOGIN_EMAIL_SCOPE,
            "limited@example.com",
            settings.jwt_signing_key,
        )
        not in remaining_fingerprints
    )
    assert (
        throttle_fingerprint(
            LOGIN_CLIENT_SCOPE,
            "127.0.0.1",
            settings.jwt_signing_key,
        )
        not in remaining_fingerprints
    )


async def test_successful_login_resets_failures_before_threshold(
    client: AsyncClient,
) -> None:
    await register_user(
        client,
        email="reset@example.com",
        password="correct passphrase",
    )
    settings = get_settings()

    for _ in range(2):
        rejected = await client.post(
            "/auth/login",
            json={"email": "reset@example.com", "password": "wrong passphrase"},
        )
        assert rejected.status_code == 401

    accepted = await client.post(
        "/auth/login",
        json={"email": "reset@example.com", "password": "correct passphrase"},
    )
    assert accepted.status_code == 200

    for _ in range(settings.login_max_attempts - 1):
        rejected = await client.post(
            "/auth/login",
            json={"email": "reset@example.com", "password": "wrong passphrase"},
        )
        assert rejected.status_code == 401

    threshold = await client.post(
        "/auth/login",
        json={"email": "reset@example.com", "password": "wrong passphrase"},
    )
    assert threshold.status_code == 429


async def test_login_throttle_limits_rotating_emails_by_client_without_raw_values(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = get_settings()
    verification_count = 0

    def reject_password(_password: str, _password_hash: str) -> bool:
        nonlocal verification_count
        verification_count += 1
        return False

    monkeypatch.setattr(auth_api, "verify_password", reject_password)
    for attempt in range(settings.login_max_attempts):
        response = await client.post(
            "/auth/login",
            json={
                "email": f"rotating-{attempt}@example.com",
                "password": "wrong passphrase",
            },
        )
        expected_status = 429 if attempt == settings.login_max_attempts - 1 else 401
        assert response.status_code == expected_status

    skipped_verification = await client.post(
        "/auth/login",
        json={"email": "another@example.com", "password": "wrong passphrase"},
    )
    assert skipped_verification.status_code == 429
    assert verification_count == settings.login_max_attempts

    async with AsyncSessionLocal() as session:
        records = (await session.scalars(select(AuthThrottle))).all()
    assert len(records) == settings.login_max_attempts + 1
    serialized_records = " ".join(
        f"{record.fingerprint} {record.failed_attempts}" for record in records
    )
    assert "rotating" not in serialized_records
    assert "example.com" not in serialized_records
    assert "127.0.0.1" not in serialized_records
    assert all(
        len(record.fingerprint) == 64 and set(record.fingerprint).issubset(set("0123456789abcdef"))
        for record in records
    )


async def test_login_throttle_canonicalizes_identity_and_serializes_concurrency(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    settings = get_settings()
    expected_identity = throttle_fingerprint(
        LOGIN_EMAIL_SCOPE,
        "mixed.case@example.com",
        settings.jwt_signing_key,
    )

    first = await client.post(
        "/auth/login",
        json={"email": " Mixed.Case@Example.COM ", "password": "wrong passphrase"},
    )
    assert first.status_code == 401
    async with AsyncSessionLocal() as session:
        identity_record = await session.get(AuthThrottle, expected_identity)
    assert identity_record is not None
    assert identity_record.failed_attempts == 1

    async with AsyncSessionLocal() as session:
        await session.execute(AuthThrottle.__table__.delete())
        await session.commit()

    monkeypatch.setattr(auth_api, "verify_password", lambda _password, _hash: False)
    responses = await asyncio.gather(
        *(
            client.post(
                "/auth/login",
                json={"email": "parallel@example.com", "password": "wrong passphrase"},
            )
            for _ in range(settings.login_max_attempts + 3)
        )
    )
    statuses = [response.status_code for response in responses]
    assert statuses.count(401) == settings.login_max_attempts - 1
    assert statuses.count(429) == 4


async def test_refresh_token_rotates_and_logout_revokes(client: AsyncClient) -> None:
    register = await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "good-password",
            "display_name": "Refresh",
        },
    )
    assert register.status_code == 201
    assert "refresh_token" not in register.json()
    first_refresh_token = register.cookies.get(REFRESH_COOKIE_NAME)
    assert first_refresh_token is not None

    refreshed = await client.post(
        "/auth/refresh",
        json={},
    )
    assert refreshed.status_code == 200
    assert "refresh_token" not in refreshed.json()
    second_refresh_token = refreshed.cookies.get(REFRESH_COOKIE_NAME)
    assert second_refresh_token is not None
    assert second_refresh_token != first_refresh_token

    client.cookies.clear()
    reused = await client.post(
        "/auth/refresh",
        json={"refresh_token": first_refresh_token},
    )
    assert reused.status_code == 401

    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200

    logout = await client.post(
        "/auth/logout",
        json={"refresh_token": second_refresh_token},
    )
    assert logout.status_code == 200
    assert f"{REFRESH_COOKIE_NAME}=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]

    revoked = await client.post(
        "/auth/refresh",
        json={"refresh_token": second_refresh_token},
    )
    assert revoked.status_code == 401


async def test_refresh_session_survives_jwt_signing_key_rotation(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    registered = await client.post(
        "/auth/register",
        json={
            "email": "rotation@example.com",
            "password": "rotation passphrase",
            "display_name": "Rotation",
        },
    )
    assert registered.status_code == 201
    old_access_token = registered.json()["access_token"]
    assert registered.cookies.get(REFRESH_COOKIE_NAME) is not None

    rotated_settings = Settings(jwt_secret="fedcba9876543210" * 4)
    monkeypatch.setattr(security_module, "get_settings", lambda: rotated_settings)

    rejected_old_access = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert rejected_old_access.status_code == 401

    refreshed = await client.post("/auth/refresh", json={})
    assert refreshed.status_code == 200
    new_access_token = refreshed.json()["access_token"]
    assert new_access_token != old_access_token

    accepted_new_access = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert accepted_new_access.status_code == 200
    assert accepted_new_access.json()["email"] == "rotation@example.com"


async def test_legacy_refresh_migration_works_with_malformed_cookie(
    client: AsyncClient,
) -> None:
    register = await client.post(
        "/auth/register",
        json={
            "email": "legacy-cookie@example.com",
            "password": "good-password",
            "display_name": "Legacy",
        },
    )
    assert register.status_code == 201
    legacy_refresh_token = register.cookies.get(REFRESH_COOKIE_NAME)
    assert legacy_refresh_token is not None
    client.cookies.clear()

    refreshed = await client.post(
        "/auth/refresh",
        json={"refresh_token": legacy_refresh_token},
        headers={"Cookie": f"{REFRESH_COOKIE_NAME}=stale"},
    )

    assert refreshed.status_code == 200
    assert "refresh_token" not in refreshed.json()
    migrated_refresh_token = refreshed.cookies.get(REFRESH_COOKIE_NAME)
    assert migrated_refresh_token is not None
    assert migrated_refresh_token != legacy_refresh_token


async def test_refresh_cookie_rejects_untrusted_browser_origin(client: AsyncClient) -> None:
    registered = await client.post(
        "/auth/register",
        json={
            "email": "origin@example.com",
            "password": "good-password",
            "display_name": "Origin",
        },
    )
    assert registered.status_code == 201

    rejected = await client.post(
        "/auth/refresh",
        json={},
        headers={"Origin": "https://untrusted.example"},
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "Request origin is not allowed."

    accepted = await client.post(
        "/auth/refresh",
        json={},
        headers={"Origin": get_settings().allowed_origins[0]},
    )
    assert accepted.status_code == 200

    blocked_registration = await client.post(
        "/auth/register",
        json={
            "email": "blocked-origin@example.com",
            "password": "good-password",
            "display_name": "Blocked",
        },
        headers={"Origin": "https://untrusted.example"},
    )
    assert blocked_registration.status_code == 403

    legacy_registered = await client.post(
        "/auth/register",
        json={
            "email": "legacy-origin@example.com",
            "password": "good-password",
            "display_name": "Legacy Origin",
        },
    )
    assert legacy_registered.status_code == 201
    legacy_refresh_token = legacy_registered.cookies.get(REFRESH_COOKIE_NAME)
    assert legacy_refresh_token is not None
    client.cookies.clear()
    rejected_legacy = await client.post(
        "/auth/refresh",
        json={"refresh_token": legacy_refresh_token},
        headers={"Origin": "https://untrusted.example"},
    )
    assert rejected_legacy.status_code == 403


async def test_protected_endpoint_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/characters")

    assert response.status_code == 401


async def test_chat_persists_user_and_assistant_messages(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assert chat.status_code == 200, chat.text
    payload = chat.json()
    assert payload["user_message"]["content"] == "Hello there"
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["assistant_message"]["metadata_json"]["provider"] == "mock"
    assert "[mock" not in payload["assistant_message"]["content"].lower()
    assert "I am here" in payload["assistant_message"]["content"]
    assert "I heard:" not in payload["assistant_message"]["content"]
    for forbidden in (
        "durable memory",
        "relationship state",
        "response plan",
        "next, i will",
        "keep the tone",
        "mood as",
        "conflict state",
        "/100",
    ):
        assert forbidden not in payload["assistant_message"]["content"].lower()

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert messages.status_code == 200
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]


async def test_conversation_read_cursor_tracks_new_assistant_messages(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    created = await client.post("/conversations", json={}, headers=headers)
    assert created.status_code == 201
    conversation = created.json()
    conversation_id = conversation["id"]
    assert conversation["unread_count"] == 0
    assert conversation["last_message_at"] is None

    first_chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "A first quiet hello."},
        headers=headers,
    )
    assert first_chat.status_code == 200
    first_assistant = first_chat.json()["assistant_message"]

    listed = await client.get("/conversations", headers=headers)
    assert listed.status_code == 200
    first_summary = listed.json()[0]
    assert first_summary["id"] == conversation_id
    assert first_summary["unread_count"] == 1
    assert first_summary["last_message_at"] == first_assistant["created_at"]

    marked = await client.post(
        f"/conversations/{conversation_id}/read",
        json={"through_message_id": first_assistant["id"]},
        headers=headers,
    )
    assert marked.status_code == 200
    first_receipt = marked.json()
    assert first_receipt["unread_count"] == 0
    assert first_receipt["last_read_at"] == first_assistant["created_at"]

    repeated = await client.post(
        f"/conversations/{conversation_id}/read",
        json={"through_message_id": first_assistant["id"]},
        headers=headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["last_read_at"] == first_receipt["last_read_at"]
    assert repeated.json()["unread_count"] == 0

    second_chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "One more thought."},
        headers=headers,
    )
    assert second_chat.status_code == 200

    relisted = await client.get("/conversations", headers=headers)
    assert relisted.status_code == 200
    assert relisted.json()[0]["unread_count"] == 1

    other_token, _ = await register_user(
        client,
        email="read-state-other@example.com",
        password="other-good-password",
    )
    forbidden = await client.post(
        f"/conversations/{conversation_id}/read",
        json={"through_message_id": first_assistant["id"]},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404

    invalid_boundary = await client.post(
        f"/conversations/{conversation_id}/read",
        json={"through_message_id": conversation_id},
        headers=headers,
    )
    assert invalid_boundary.status_code == 404


async def test_stream_persists_final_assistant_without_duplicate(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    async with client.stream(
        "POST",
        "/chat/stream",
        json={"conversation_id": conversation_id, "content": "Please remember that I like tea."},
        headers=headers,
    ) as response:
        body = await response.aread()

    assert response.status_code == 200
    text = body.decode()
    assert "event: message_start" in text
    assert "event: token" in text
    assert "event: message_done" in text
    assert text.index("event: message_start") < text.index("event: token")
    assert text.rindex("event: token") < text.index("event: message_done")
    assert text.count("event: token") > 2

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert [message["role"] for message in messages.json()] == ["user", "assistant"]
    assistant_content = messages.json()[-1]["content"].lower()
    assert "durable memory" not in assistant_content
    assert "response plan" not in assistant_content
    assert "relationship state" not in assistant_content
    assert "next, i will" not in assistant_content

    characters = await client.get("/characters", headers=headers)
    character_id = characters.json()[0]["id"]
    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    assert len(memories.json()) == 1
    debug = await client.get(f"/debug/conversation/{conversation_id}", headers=headers)
    assert debug.status_code == 200
    assert debug.json()["last_assembled_context"]["generation_kind"] == "stream"


async def test_stream_accepts_one_private_turn_without_changing_thread_mode(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    async with client.stream(
        "POST",
        "/chat/stream",
        json={
            "conversation_id": conversation_id,
            "content": "Please remember that the private marker is winter glass.",
            "privacy_mode": "private",
        },
        headers=headers,
    ) as response:
        body = await response.aread()

    assert response.status_code == 200
    assert "event: message_start" in body.decode()
    history = await client.get(
        f"/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert history.status_code == 200
    assert [message["metadata_json"]["privacy_mode"] for message in history.json()] == [
        "private",
        "private",
    ]

    summaries = await client.get("/conversations", headers=headers)
    assert summaries.status_code == 200
    assert summaries.json()[0]["metadata_json"]["privacy_mode"] == "normal"

    character_id = conversation.json()["character_id"]
    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    assert memories.json() == []

    invalid = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "This request should not be accepted.",
            "privacy_mode": "ephemeral",
        },
        headers=headers,
    )
    assert invalid.status_code == 422


async def test_message_remember_is_source_linked_idempotent_and_account_scoped(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "The cedar box belongs beside the window.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    user_message = chat.json()["user_message"]
    assistant_message = chat.json()["assistant_message"]

    remembered = await client.post(
        f"/conversations/{conversation_id}/messages/{user_message['id']}/remember",
        headers=headers,
    )
    assert remembered.status_code == 200
    first_memory = remembered.json()
    assert first_memory["source_message_id"] == user_message["id"]
    assert first_memory["memory_type"] == "event"
    assert first_memory["pinned"] is True
    assert first_memory["metadata_json"]["source"] == "user_saved"
    assert first_memory["metadata_json"]["capture"]["reason"] == "user_saved"
    assert first_memory["metadata_json"]["capture"]["source_role"] == "user"
    assert user_message["id"] in first_memory["metadata_json"]["source_message_ids"]

    repeated = await client.post(
        f"/conversations/{conversation_id}/messages/{user_message['id']}/remember",
        headers=headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == first_memory["id"]
    assert repeated.json()["updated_at"] == first_memory["updated_at"]

    character_id = conversation.json()["character_id"]
    forgotten = await client.post(
        f"/characters/{character_id}/memories/{first_memory['id']}/forget",
        headers=headers,
    )
    assert forgotten.status_code == 200
    assert forgotten.json()["forgotten_at"] is not None

    revived = await client.post(
        f"/conversations/{conversation_id}/messages/{user_message['id']}/remember",
        headers=headers,
    )
    assert revived.status_code == 200
    assert revived.json()["id"] == first_memory["id"]
    assert revived.json()["forgotten_at"] is None
    assert revived.json()["metadata_json"]["last_restore_reason"] == "remembered_by_user"

    remembered_reply = await client.post(
        f"/conversations/{conversation_id}/messages/{assistant_message['id']}/remember",
        headers=headers,
    )
    assert remembered_reply.status_code == 200
    assert remembered_reply.json()["memory_type"] == "shared_moment"
    assert remembered_reply.json()["metadata_json"]["capture"]["source_role"] == "assistant"

    memories = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert memories.status_code == 200
    assert len(memories.json()) == 2

    other_token, _ = await register_user(
        client,
        email="remember-other@example.com",
        password="other-good-password",
    )
    forbidden = await client.post(
        f"/conversations/{conversation_id}/messages/{user_message['id']}/remember",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 404


async def test_message_remember_promotes_automatic_memory_without_duplicate(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    character_id = conversation.json()["character_id"]
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Please remember that I like cedar tea.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    message_id = chat.json()["user_message"]["id"]

    before = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert before.status_code == 200
    assert len(before.json()) == 1
    automatic_memory = before.json()[0]
    assert automatic_memory["metadata_json"]["source"] == "extracted"
    assert automatic_memory["pinned"] is False

    remembered = await client.post(
        f"/conversations/{conversation_id}/messages/{message_id}/remember",
        headers=headers,
    )
    assert remembered.status_code == 200
    assert remembered.json()["id"] == automatic_memory["id"]
    assert remembered.json()["metadata_json"]["source"] == "user_saved"
    assert remembered.json()["pinned"] is True

    after = await client.get(f"/characters/{character_id}/memories", headers=headers)
    assert after.status_code == 200
    assert len(after.json()) == 1


async def test_message_remember_preserves_original_private_mode(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post(
        "/conversations",
        json={"privacy_mode": "private"},
        headers=headers,
    )
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "The blue notebook can stay in this room.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    message_id = chat.json()["user_message"]["id"]

    blocked_while_private = await client.post(
        f"/conversations/{conversation_id}/messages/{message_id}/remember",
        headers=headers,
    )
    assert blocked_while_private.status_code == 409
    assert "private thread" in blocked_while_private.json()["detail"].lower()

    standard = await client.patch(
        f"/conversations/{conversation_id}",
        json={"privacy_mode": "normal"},
        headers=headers,
    )
    assert standard.status_code == 200

    blocked_after_switch = await client.post(
        f"/conversations/{conversation_id}/messages/{message_id}/remember",
        headers=headers,
    )
    assert blocked_after_switch.status_code == 409

    memories = await client.get(
        f"/characters/{conversation.json()['character_id']}/memories",
        headers=headers,
    )
    assert memories.status_code == 200
    assert memories.json() == []


async def test_message_remember_respects_adult_memory_opt_in(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    age_gate = await client.patch(
        "/auth/me",
        json={"age_gate_confirmed": True},
        headers=headers,
    )
    assert age_gate.status_code == 200

    character = (await client.get("/characters", headers=headers)).json()[0]
    character_id = character["id"]
    adult_ready = await client.patch(
        f"/characters/{character_id}",
        json={
            "explicit_age": 29,
            "adult_mode_allowed": True,
            "boundaries_json": {
                **character["boundaries_json"],
                "memory_preferences": {
                    **character["boundaries_json"]["memory_preferences"],
                    "adult_memory_storage": False,
                },
            },
        },
        headers=headers,
    )
    assert adult_ready.status_code == 200

    conversation = await client.post(
        "/conversations",
        json={"character_id": character_id},
        headers=headers,
    )
    conversation_id = conversation.json()["id"]
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "Keep this as a calm structural boundary check.",
            "content_mode": "adult",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    message = chat.json()["user_message"]
    assert message["metadata_json"]["content_mode"] == "adult"

    blocked = await client.post(
        f"/conversations/{conversation_id}/messages/{message['id']}/remember",
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "adult memory storage" in blocked.json()["detail"].lower()

    enabled = await client.patch(
        f"/characters/{character_id}",
        json={
            "boundaries_json": {
                **adult_ready.json()["boundaries_json"],
                "memory_preferences": {
                    **adult_ready.json()["boundaries_json"]["memory_preferences"],
                    "adult_memory_storage": True,
                },
            }
        },
        headers=headers,
    )
    assert enabled.status_code == 200

    remembered = await client.post(
        f"/conversations/{conversation_id}/messages/{message['id']}/remember",
        headers=headers,
    )
    assert remembered.status_code == 200
    assert remembered.json()["source_message_id"] == message["id"]


async def test_message_remember_rejects_credential_like_content(
    client: AsyncClient,
) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]
    chat = await client.post(
        "/chat/messages",
        json={
            "conversation_id": conversation_id,
            "content": "The password clue belongs in the red notebook.",
        },
        headers=headers,
    )
    assert chat.status_code == 200

    blocked = await client.post(
        (f"/conversations/{conversation_id}/messages/{chat.json()['user_message']['id']}/remember"),
        headers=headers,
    )
    assert blocked.status_code == 422
    assert "credential" in blocked.json()["detail"].lower()


async def test_delete_single_message_is_conversation_scoped(client: AsyncClient) -> None:
    headers = await auth_headers(client)
    conversation = await client.post("/conversations", json={}, headers=headers)
    conversation_id = conversation.json()["id"]

    chat = await client.post(
        "/chat/messages",
        json={"conversation_id": conversation_id, "content": "Hello there"},
        headers=headers,
    )
    assert chat.status_code == 200
    assistant_id = chat.json()["assistant_message"]["id"]

    other_token, _ = await register_user(
        client,
        email="other@example.com",
        password="other-good-password",
    )
    other_headers = {"Authorization": f"Bearer {other_token}"}
    forbidden = await client.delete(
        f"/conversations/{conversation_id}/messages/{assistant_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 404

    deleted = await client.delete(
        f"/conversations/{conversation_id}/messages/{assistant_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
    assert [message["role"] for message in messages.json()] == ["user"]
