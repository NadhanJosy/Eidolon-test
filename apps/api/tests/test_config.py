from __future__ import annotations

from app.config import Settings


def test_allowed_origins_include_web_origin_and_cors_origins() -> None:
    settings = Settings(
        web_origin="https://sample-3000.app.github.dev/",
        cors_origins="http://localhost:3000, https://sample-3000.app.github.dev/",
    )

    assert settings.allowed_origins == [
        "http://localhost:3000",
        "https://sample-3000.app.github.dev",
    ]


def test_invalid_llm_provider_is_rejected() -> None:
    try:
        Settings(llm_provider="paid-api")
    except ValueError as exc:
        assert "LLM_PROVIDER" in str(exc)
    else:
        raise AssertionError("Expected invalid provider to be rejected.")


def test_production_placeholder_jwt_secret_is_rejected() -> None:
    try:
        Settings(app_env="production", jwt_secret="change-me-in-real-env")
    except ValueError as exc:
        assert "JWT_SECRET" in str(exc)
    else:
        raise AssertionError("Expected placeholder production secret to be rejected.")
