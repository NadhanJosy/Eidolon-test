from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pytest import MonkeyPatch

from app import security
from app.config import Settings

VALID_JWT_SECRET = "0123456789abcdef" * 4
OTHER_JWT_SECRET = "fedcba9876543210" * 4


def test_access_token_round_trip_requires_complete_claim_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(jwt_secret=VALID_JWT_SECRET, jwt_access_token_expire_minutes=15)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    user_id = uuid.uuid4()

    token = security.create_access_token(user_id)
    claims = jwt.decode(
        token,
        settings.jwt_signing_key,
        algorithms=[security.ALGORITHM],
        audience=security.ACCESS_TOKEN_AUDIENCE,
        issuer=security.ACCESS_TOKEN_ISSUER,
    )

    assert security.decode_access_token(token) == user_id
    assert claims["sub"] == str(user_id)
    assert claims["iss"] == security.ACCESS_TOKEN_ISSUER
    assert claims["aud"] == security.ACCESS_TOKEN_AUDIENCE
    assert claims["type"] == security.ACCESS_TOKEN_TYPE
    assert uuid.UUID(claims["jti"])
    assert 895 <= claims["exp"] - claims["iat"] <= 900
    assert claims["nbf"] == claims["iat"]


def test_access_token_rejects_missing_and_semantically_invalid_claims(
    monkeypatch: MonkeyPatch,
) -> None:
    settings = Settings(jwt_secret=VALID_JWT_SECRET)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    valid_payload = _access_payload(user_id, now)

    for claim in security.REQUIRED_ACCESS_TOKEN_CLAIMS:
        incomplete = {key: value for key, value in valid_payload.items() if key != claim}
        assert security.decode_access_token(_encode(incomplete, settings)) is None

    invalid_payloads = (
        {**valid_payload, "iss": "another-api"},
        {**valid_payload, "aud": "another-client"},
        {**valid_payload, "type": "refresh"},
        {**valid_payload, "sub": "not-a-uuid"},
        {**valid_payload, "jti": "not-a-uuid"},
        {**valid_payload, "exp": now - timedelta(seconds=10)},
        {**valid_payload, "iat": now + timedelta(seconds=10)},
        {**valid_payload, "nbf": now + timedelta(seconds=10)},
    )
    for payload in invalid_payloads:
        assert security.decode_access_token(_encode(payload, settings)) is None


def test_access_token_rejects_wrong_key_and_algorithm(monkeypatch: MonkeyPatch) -> None:
    settings = Settings(jwt_secret=VALID_JWT_SECRET)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    payload = _access_payload(uuid.uuid4(), datetime.now(UTC))

    wrong_key = jwt.encode(payload, OTHER_JWT_SECRET, algorithm=security.ALGORITHM)
    wrong_algorithm = jwt.encode(payload, settings.jwt_signing_key, algorithm="HS384")

    assert security.decode_access_token(wrong_key) is None
    assert security.decode_access_token(wrong_algorithm) is None
    assert security.decode_access_token("not-a-jwt") is None


def _access_payload(user_id: uuid.UUID, now: datetime) -> dict[str, object]:
    return {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "nbf": now,
        "iss": security.ACCESS_TOKEN_ISSUER,
        "aud": security.ACCESS_TOKEN_AUDIENCE,
        "type": security.ACCESS_TOKEN_TYPE,
        "jti": str(uuid.uuid4()),
    }


def _encode(payload: dict[str, object], settings: Settings) -> str:
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=security.ALGORITHM)
