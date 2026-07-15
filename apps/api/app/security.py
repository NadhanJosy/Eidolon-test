from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_ISSUER = "eidolon-api"
ACCESS_TOKEN_AUDIENCE = "eidolon-web"
ACCESS_TOKEN_TYPE = "access"
ACCESS_TOKEN_LEEWAY_SECONDS = 5
REQUIRED_ACCESS_TOKEN_CLAIMS = (
    "sub",
    "exp",
    "iat",
    "nbf",
    "iss",
    "aud",
    "type",
    "jti",
)
password_hasher = PasswordHasher()
MAX_EMAIL_LENGTH = 320
MAX_EMAIL_LOCAL_LENGTH = 64
MAX_EMAIL_DOMAIN_LENGTH = 253
EMAIL_LOCAL_PATTERN = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$", re.ASCII)
EMAIL_DOMAIN_LABEL_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.ASCII,
)
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$1UMrJRXKpsnGGTXKT31VDA$"
    "pEi0sBHGFIF7bWfRo/M2Phxu/a46AlG6jI3gQDhZcFg"
)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or len(normalized) > MAX_EMAIL_LENGTH:
        raise ValueError("Enter a valid email address.")
    if normalized.count("@") != 1:
        raise ValueError("Enter a valid email address.")

    local_part, domain = normalized.split("@", maxsplit=1)
    if (
        not local_part
        or len(local_part) > MAX_EMAIL_LOCAL_LENGTH
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or EMAIL_LOCAL_PATTERN.fullmatch(local_part) is None
    ):
        raise ValueError("Enter a valid email address.")

    labels = domain.split(".")
    if (
        len(domain) > MAX_EMAIL_DOMAIN_LENGTH
        or len(labels) < 2
        or any(EMAIL_DOMAIN_LABEL_PATTERN.fullmatch(label) is None for label in labels)
    ):
        raise ValueError("Enter a valid email address.")
    return normalized


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError, VerificationError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": issued_at,
        "nbf": issued_at,
        "iss": ACCESS_TOKEN_ISSUER,
        "aud": ACCESS_TOKEN_AUDIENCE,
        "type": ACCESS_TOKEN_TYPE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_signing_key, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    return token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> uuid.UUID | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_signing_key,
            algorithms=[ALGORITHM],
            audience=ACCESS_TOKEN_AUDIENCE,
            issuer=ACCESS_TOKEN_ISSUER,
            leeway=ACCESS_TOKEN_LEEWAY_SECONDS,
            options={"require": list(REQUIRED_ACCESS_TOKEN_CLAIMS)},
        )
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None
        subject = payload.get("sub")
        token_id = payload.get("jti")
        if not isinstance(subject, str) or not isinstance(token_id, str):
            return None
        uuid.UUID(token_id)
        return uuid.UUID(subject)
    except (jwt.PyJWTError, ValueError):
        return None
