from __future__ import annotations

from app.config import Settings

VALID_JWT_SECRET = "0123456789abcdef" * 4


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


def test_groq_configuration_requires_and_masks_server_side_key() -> None:
    try:
        Settings(llm_provider="groq", groq_api_key=None)
    except ValueError as exc:
        assert "GROQ_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing GROQ_API_KEY to be rejected.")

    key = "gsk_private_test_value"
    settings = Settings(
        llm_provider="groq",
        groq_api_key=key,
        groq_model="llama-3.3-70b-versatile",
    )
    assert settings.groq_signing_key == key
    assert key not in repr(settings)
    assert "**********" in repr(settings)


def test_live_provider_cannot_fall_back_to_mock_text() -> None:
    try:
        Settings(
            llm_provider="groq",
            groq_api_key="gsk_private_test_value",
            llm_fallback_provider="mock",
        )
    except ValueError as exc:
        assert "mock" in str(exc)
    else:
        raise AssertionError("Expected live-to-mock fallback to be rejected.")


def test_llm_generation_bounds_are_validated() -> None:
    invalid_settings = (
        ({"llm_temperature": 0}, "LLM_TEMPERATURE"),
        ({"llm_max_output_tokens": 0}, "LLM_MAX_OUTPUT_TOKENS"),
        ({"llm_timeout_seconds": 0}, "LLM_TIMEOUT_SECONDS"),
        ({"llm_context_budget_tokens": 100}, "LLM_CONTEXT_BUDGET_TOKENS"),
        ({"llm_max_retries": 6}, "LLM_MAX_RETRIES"),
    )
    for overrides, expected_label in invalid_settings:
        try:
            Settings(**overrides)
        except ValueError as exc:
            assert expected_label in str(exc)
        else:
            raise AssertionError(f"Expected {expected_label} validation to fail.")


def test_production_placeholder_jwt_secret_is_rejected() -> None:
    try:
        Settings(
            app_env="production",
            llm_provider="ollama",
            jwt_secret="change-me-in-real-env-use-32-plus-bytes",
            refresh_cookie_secure=True,
        )
    except ValueError as exc:
        assert "JWT_SECRET" in str(exc)
    else:
        raise AssertionError("Expected placeholder production secret to be rejected.")


def test_debug_routes_require_explicit_production_opt_in() -> None:
    production = Settings(
        app_env="production",
        llm_provider="ollama",
        jwt_secret=VALID_JWT_SECRET,
        refresh_cookie_secure=True,
    )
    enabled = Settings(
        app_env="production",
        llm_provider="ollama",
        jwt_secret=VALID_JWT_SECRET,
        enable_debug_routes=True,
        refresh_cookie_secure=True,
    )
    testing = Settings(app_env="testing")

    assert production.debug_routes_available is False
    assert enabled.debug_routes_available is True
    assert testing.debug_routes_available is True


def test_refresh_token_lifetime_must_be_positive() -> None:
    try:
        Settings(jwt_refresh_token_expire_days=0)
    except ValueError as exc:
        assert "JWT_REFRESH_TOKEN_EXPIRE_DAYS" in str(exc)
    else:
        raise AssertionError("Expected invalid refresh-token lifetime to be rejected.")


def test_refresh_cookie_security_settings_are_validated() -> None:
    normalized = Settings(refresh_cookie_samesite=" Lax ")
    assert normalized.refresh_cookie_samesite == "lax"

    invalid_settings = (
        (
            {
                "app_env": "production",
                "llm_provider": "ollama",
                "jwt_secret": VALID_JWT_SECRET,
                "refresh_cookie_secure": False,
            },
            "REFRESH_COOKIE_SECURE",
        ),
        (
            {
                "refresh_cookie_samesite": "none",
                "refresh_cookie_secure": False,
            },
            "REFRESH_COOKIE_SECURE",
        ),
        (
            {"refresh_cookie_samesite": "sometimes"},
            "REFRESH_COOKIE_SAMESITE",
        ),
        (
            {"jwt_access_token_expire_minutes": 0},
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    for overrides, expected_label in invalid_settings:
        try:
            Settings(**overrides)
        except ValueError as exc:
            assert expected_label in str(exc)
        else:
            raise AssertionError(f"Expected {expected_label} validation to fail.")


def test_jwt_secret_byte_bounds_and_masked_representation() -> None:
    invalid_secrets = (
        "a" * 31,
        "é" * 15,
        "a" * 4097,
    )
    for secret in invalid_secrets:
        try:
            Settings(jwt_secret=secret)
        except ValueError as exc:
            assert "JWT_SECRET" in str(exc)
            assert secret not in str(exc)
        else:
            raise AssertionError("Expected invalid JWT_SECRET byte length to fail.")

    multibyte_boundary = Settings(jwt_secret="é" * 16)
    assert len(multibyte_boundary.jwt_signing_key.encode("utf-8")) == 32
    assert multibyte_boundary.jwt_signing_key not in repr(multibyte_boundary)
    assert "**********" in repr(multibyte_boundary)


def test_production_jwt_secret_rejects_markers_and_low_diversity() -> None:
    invalid_secrets = (
        "change-me-" + "0123456789abcdef" * 2,
        "replace_this_" + "0123456789abcdef" * 2,
        "a" * 64,
    )
    for secret in invalid_secrets:
        try:
            Settings(
                app_env="production",
                llm_provider="ollama",
                jwt_secret=secret,
                refresh_cookie_secure=True,
            )
        except ValueError as exc:
            assert "JWT_SECRET" in str(exc)
            assert secret not in str(exc)
        else:
            raise AssertionError("Expected weak production JWT_SECRET to fail.")


def test_scheduler_runtime_bounds_are_validated() -> None:
    invalid_settings = (
        ({"scheduler_interval_seconds": 4}, "SCHEDULER_INTERVAL_SECONDS"),
        ({"scheduler_job_limit": 101}, "SCHEDULER_JOB_LIMIT"),
        ({"scheduler_max_retries": 11}, "SCHEDULER_MAX_RETRIES"),
        ({"scheduler_retry_base_seconds": 4}, "SCHEDULER_RETRY_BASE_SECONDS"),
    )
    for overrides, expected_label in invalid_settings:
        try:
            Settings(**overrides)
        except ValueError as exc:
            assert expected_label in str(exc)
        else:
            raise AssertionError(f"Expected {expected_label} validation to fail.")


def test_login_throttle_runtime_bounds_are_validated() -> None:
    invalid_settings = (
        ({"login_max_attempts": 2}, "LOGIN_MAX_ATTEMPTS"),
        ({"login_max_attempts": 21}, "LOGIN_MAX_ATTEMPTS"),
        ({"login_attempt_window_seconds": 59}, "LOGIN_ATTEMPT_WINDOW_SECONDS"),
        ({"login_attempt_window_seconds": 86401}, "LOGIN_ATTEMPT_WINDOW_SECONDS"),
        ({"login_block_seconds": 59}, "LOGIN_BLOCK_SECONDS"),
        ({"login_block_seconds": 86401}, "LOGIN_BLOCK_SECONDS"),
    )
    for overrides, expected_label in invalid_settings:
        try:
            Settings(**overrides)
        except ValueError as exc:
            assert expected_label in str(exc)
        else:
            raise AssertionError(f"Expected {expected_label} validation to fail.")


def test_registration_throttle_runtime_bounds_are_validated() -> None:
    invalid_settings = (
        ({"registration_max_attempts": 0}, "REGISTRATION_MAX_ATTEMPTS"),
        ({"registration_max_attempts": 21}, "REGISTRATION_MAX_ATTEMPTS"),
        (
            {"registration_attempt_window_seconds": 59},
            "REGISTRATION_ATTEMPT_WINDOW_SECONDS",
        ),
        (
            {"registration_attempt_window_seconds": 86401},
            "REGISTRATION_ATTEMPT_WINDOW_SECONDS",
        ),
        ({"registration_block_seconds": 59}, "REGISTRATION_BLOCK_SECONDS"),
        ({"registration_block_seconds": 86401}, "REGISTRATION_BLOCK_SECONDS"),
    )
    for overrides, expected_label in invalid_settings:
        try:
            Settings(**overrides)
        except ValueError as exc:
            assert expected_label in str(exc)
        else:
            raise AssertionError(f"Expected {expected_label} validation to fail.")
