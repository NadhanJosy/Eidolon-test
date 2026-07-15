from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Sequence

EMBEDDING_DIMENSIONS = 384
EMBEDDING_VERSION = "local-feature-v1"
MAX_EMBEDDING_TEXT_CHARS = 4000

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "user",
    "was",
    "were",
    "with",
}
_CONCEPT_GROUPS = {
    "calm": {
        "calm",
        "calming",
        "gentle",
        "peaceful",
        "quiet",
        "serene",
        "soft",
        "soothing",
        "stillness",
    },
    "conversation": {
        "chat",
        "chats",
        "conversation",
        "conversations",
        "dialogue",
        "talk",
        "talking",
    },
    "difficult": {
        "difficult",
        "hard",
        "heavy",
        "overwhelming",
        "rough",
        "stressful",
        "tough",
    },
    "happy": {
        "bright",
        "cheerful",
        "delighted",
        "glad",
        "happy",
        "joy",
        "joyful",
    },
    "sad": {
        "down",
        "grief",
        "low",
        "melancholy",
        "sad",
        "sorrow",
        "unhappy",
    },
    "tired": {
        "drained",
        "exhausted",
        "fatigued",
        "sleepy",
        "tired",
        "weary",
    },
}
_TOKEN_CONCEPT = {token: concept for concept, tokens in _CONCEPT_GROUPS.items() for token in tokens}


def text_embedding(text: str) -> list[float]:
    """Build a deterministic, dependency-free feature vector for hybrid recall."""
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    tokens = [
        token
        for token in _TOKEN_RE.findall(normalized[:MAX_EMBEDDING_TEXT_CHARS])
        if len(token) > 1 and token not in _STOP_WORDS
    ]
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in tokens:
        _add_feature(vector, f"token:{token}", 1.0)
        stem = _light_stem(token)
        if stem != token:
            _add_feature(vector, f"stem:{stem}", 0.55)
        concept = _TOKEN_CONCEPT.get(token) or _TOKEN_CONCEPT.get(stem)
        if concept is not None:
            _add_feature(vector, f"concept:{concept}", 1.6)
        if len(token) >= 5:
            for index in range(len(token) - 2):
                _add_feature(vector, f"gram:{token[index : index + 3]}", 0.12)
    for left, right in zip(tokens, tokens[1:], strict=False):
        _add_feature(vector, f"pair:{_light_stem(left)}:{_light_stem(right)}", 0.35)
    return _normalize(vector)


def coerce_embedding(value: object) -> list[float] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)):
        return None
    if len(value) != EMBEDDING_DIMENSIONS:
        return None
    converted: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        converted.append(number)
    return converted


def cosine_similarity(left: object, right: object) -> float:
    left_vector = coerce_embedding(left)
    right_vector = coerce_embedding(right)
    if left_vector is None or right_vector is None:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    similarity = sum(
        left_value * right_value
        for left_value, right_value in zip(left_vector, right_vector, strict=True)
    ) / (left_norm * right_norm)
    return max(-1.0, min(1.0, similarity))


def _add_feature(vector: list[float], feature: str, weight: float) -> None:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
    sign = 1.0 if digest[4] & 1 else -1.0
    vector[index] += weight * sign


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        return vector
    return [value / norm for value in vector]


def _light_stem(token: str) -> str:
    for suffix, minimum_length in (("ing", 6), ("ies", 6), ("ed", 5), ("es", 5), ("s", 4)):
        if token.endswith(suffix) and len(token) >= minimum_length:
            if suffix == "ies":
                return f"{token[:-3]}y"
            return token[: -len(suffix)]
    return token
