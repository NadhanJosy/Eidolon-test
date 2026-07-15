from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://eidolon:eidolon_dev_password@localhost:5432/eidolon"
DEFAULT_JWT_SECRET = "change-me-in-real-env-use-32-plus-bytes"
MIN_JWT_SECRET_BYTES = 32
MAX_JWT_SECRET_BYTES = 4096
WEAK_JWT_SECRET_MARKERS = ("change-me", "changeme", "replace-me", "replace_this")


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Eidolon"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    cors_origins: str = ""
    enable_debug_routes: bool = False

    database_url: str = DEFAULT_DATABASE_URL
    database_pool_size: int = 5
    database_max_overflow: int = 0
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 300

    jwt_secret: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    login_max_attempts: int = 5
    login_attempt_window_seconds: int = 900
    login_block_seconds: int = 900
    registration_max_attempts: int = 5
    registration_attempt_window_seconds: int = 900
    registration_block_seconds: int = 900

    llm_provider: str = "groq"
    llm_temperature: float = 0.8
    llm_max_output_tokens: int = 1200
    llm_timeout_seconds: float = 45.0
    llm_context_budget_tokens: int = 8000
    llm_max_retries: int = 2
    llm_retry_base_seconds: float = 0.5
    llm_fallback_provider: str | None = None
    llm_fallback_model: str | None = None

    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    enable_scheduler: bool = True
    scheduler_interval_seconds: int = 60
    scheduler_job_limit: int = 10
    scheduler_max_retries: int = 3
    scheduler_retry_base_seconds: int = 30
    proactive_inactivity_hours: int = 24
    proactive_cooldown_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if normalized.startswith("postgres://"):
            normalized = f"postgresql+asyncpg://{normalized.removeprefix('postgres://')}"
        elif normalized.startswith("postgresql://"):
            normalized = f"postgresql+asyncpg://{normalized.removeprefix('postgresql://')}"
        return _normalize_asyncpg_ssl_query(normalized)

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Settings:
        self.app_env = self.app_env.strip().lower()
        self.refresh_cookie_samesite = self.refresh_cookie_samesite.strip().lower()
        jwt_secret = self.jwt_secret.get_secret_value()
        jwt_secret_bytes = len(jwt_secret.encode("utf-8"))
        if not MIN_JWT_SECRET_BYTES <= jwt_secret_bytes <= MAX_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET must be between {MIN_JWT_SECRET_BYTES} and "
                f"{MAX_JWT_SECRET_BYTES} UTF-8 bytes."
            )
        self.llm_provider = self.llm_provider.strip().lower()
        if self.llm_fallback_provider is not None:
            normalized_fallback = self.llm_fallback_provider.strip().lower()
            self.llm_fallback_provider = normalized_fallback or None
        supported_providers = {"groq", "mock", "ollama"}
        if self.llm_provider not in supported_providers:
            raise ValueError("LLM_PROVIDER must be groq, mock, or ollama.")
        if (
            self.llm_fallback_provider is not None
            and self.llm_fallback_provider not in supported_providers
        ):
            raise ValueError("LLM_FALLBACK_PROVIDER must be groq, mock, or ollama.")
        if self.llm_provider == "groq" and not self.groq_signing_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")
        if self.llm_fallback_provider == "groq" and not self.groq_signing_key:
            raise ValueError("GROQ_API_KEY is required when the fallback provider is groq.")
        if self.llm_provider != "mock" and self.llm_fallback_provider == "mock":
            raise ValueError("A live provider cannot fall back to generated mock text.")
        if self.llm_provider == "mock" and self.app_env not in {"development", "testing"}:
            raise ValueError("LLM_PROVIDER=mock is allowed only in development or testing.")
        if not 0 < self.llm_temperature <= 2:
            raise ValueError("LLM_TEMPERATURE must be greater than 0 and at most 2.")
        if not 1 <= self.llm_max_output_tokens <= 32768:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be between 1 and 32768.")
        if not 1 <= self.llm_timeout_seconds <= 300:
            raise ValueError("LLM_TIMEOUT_SECONDS must be between 1 and 300.")
        if not 1024 <= self.llm_context_budget_tokens <= 120000:
            raise ValueError("LLM_CONTEXT_BUDGET_TOKENS must be between 1024 and 120000.")
        if not 0 <= self.llm_max_retries <= 5:
            raise ValueError("LLM_MAX_RETRIES must be between 0 and 5.")
        if not 0.05 <= self.llm_retry_base_seconds <= 10:
            raise ValueError("LLM_RETRY_BASE_SECONDS must be between 0.05 and 10.")
        if not self.groq_model.strip():
            raise ValueError("GROQ_MODEL cannot be empty.")
        if not self.ollama_model.strip():
            raise ValueError("OLLAMA_MODEL cannot be empty.")
        if self.app_env not in {"development", "testing"}:
            normalized_secret = jwt_secret.casefold()
            if jwt_secret == DEFAULT_JWT_SECRET or any(
                marker in normalized_secret for marker in WEAK_JWT_SECRET_MARKERS
            ):
                raise ValueError(
                    "JWT_SECRET must be replaced with a private random value outside "
                    "development/testing."
                )
            if len(set(jwt_secret)) < 8:
                raise ValueError(
                    "JWT_SECRET must have sufficient character diversity outside "
                    "development/testing."
                )
        if self.scheduler_interval_seconds < 5:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be at least 5.")
        if self.scheduler_interval_seconds > 3600:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be at most 3600.")
        if self.scheduler_job_limit < 1:
            raise ValueError("SCHEDULER_JOB_LIMIT must be at least 1.")
        if self.scheduler_job_limit > 100:
            raise ValueError("SCHEDULER_JOB_LIMIT must be at most 100.")
        if not 0 <= self.scheduler_max_retries <= 10:
            raise ValueError("SCHEDULER_MAX_RETRIES must be between 0 and 10.")
        if not 5 <= self.scheduler_retry_base_seconds <= 3600:
            raise ValueError("SCHEDULER_RETRY_BASE_SECONDS must be between 5 and 3600.")
        if self.proactive_inactivity_hours < 1:
            raise ValueError("PROACTIVE_INACTIVITY_HOURS must be at least 1.")
        if self.proactive_cooldown_hours < 1:
            raise ValueError("PROACTIVE_COOLDOWN_HOURS must be at least 1.")
        if self.jwt_refresh_token_expire_days < 1:
            raise ValueError("JWT_REFRESH_TOKEN_EXPIRE_DAYS must be at least 1.")
        if not 1 <= self.jwt_access_token_expire_minutes <= 1440:
            raise ValueError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440.")
        if self.refresh_cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("REFRESH_COOKIE_SAMESITE must be lax, strict, or none.")
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true when SameSite is none.")
        if self.app_env not in {"development", "testing"} and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true outside development/testing.")
        if self.app_env not in {"development", "testing"}:
            if self.database_url == DEFAULT_DATABASE_URL:
                raise ValueError("DATABASE_URL must be set explicitly outside development/testing.")
            database = urlsplit(self.database_url)
            if (
                database.scheme != "postgresql+asyncpg"
                or not database.hostname
                or database.path in {"", "/"}
            ):
                raise ValueError(
                    "DATABASE_URL must be a PostgreSQL URL using the asyncpg driver outside "
                    "development/testing."
                )
            if self.llm_provider != "groq":
                raise ValueError("LLM_PROVIDER must be groq outside development/testing.")
            if not self.groq_signing_key:
                raise ValueError("GROQ_API_KEY is required outside development/testing.")
            origins = self.allowed_origins
            if not origins or "*" in origins:
                raise ValueError("An explicit WEB_ORIGIN or CORS_ORIGINS value is required.")
            if any(not _is_secure_origin(origin) for origin in origins):
                raise ValueError("Production browser origins must use HTTPS and contain no path.")
        if not 1 <= self.database_pool_size <= 20:
            raise ValueError("DATABASE_POOL_SIZE must be between 1 and 20.")
        if not 0 <= self.database_max_overflow <= 20:
            raise ValueError("DATABASE_MAX_OVERFLOW must be between 0 and 20.")
        if not 1 <= self.database_pool_timeout_seconds <= 120:
            raise ValueError("DATABASE_POOL_TIMEOUT_SECONDS must be between 1 and 120.")
        if not 30 <= self.database_pool_recycle_seconds <= 3600:
            raise ValueError("DATABASE_POOL_RECYCLE_SECONDS must be between 30 and 3600.")
        if not 3 <= self.login_max_attempts <= 20:
            raise ValueError("LOGIN_MAX_ATTEMPTS must be between 3 and 20.")
        if not 60 <= self.login_attempt_window_seconds <= 86400:
            raise ValueError("LOGIN_ATTEMPT_WINDOW_SECONDS must be between 60 and 86400.")
        if not 60 <= self.login_block_seconds <= 86400:
            raise ValueError("LOGIN_BLOCK_SECONDS must be between 60 and 86400.")
        if not 1 <= self.registration_max_attempts <= 20:
            raise ValueError("REGISTRATION_MAX_ATTEMPTS must be between 1 and 20.")
        if not 60 <= self.registration_attempt_window_seconds <= 86400:
            raise ValueError("REGISTRATION_ATTEMPT_WINDOW_SECONDS must be between 60 and 86400.")
        if not 60 <= self.registration_block_seconds <= 86400:
            raise ValueError("REGISTRATION_BLOCK_SECONDS must be between 60 and 86400.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        origins = [_normalize_origin(self.web_origin)]
        origins.extend(_normalize_origin(origin) for origin in self.cors_origins.split(","))
        origins = [origin for origin in origins if origin]
        return sorted(set(origins))

    @property
    def debug_routes_available(self) -> bool:
        return self.enable_debug_routes or self.app_env in {"development", "testing"}

    @property
    def refresh_token_lifetime(self) -> timedelta:
        return timedelta(days=self.jwt_refresh_token_expire_days)

    @property
    def refresh_cookie_max_age_seconds(self) -> int:
        return int(self.refresh_token_lifetime.total_seconds())

    @property
    def jwt_signing_key(self) -> str:
        return self.jwt_secret.get_secret_value()

    @property
    def groq_signing_key(self) -> str:
        if self.groq_api_key is None:
            return ""
        return self.groq_api_key.get_secret_value().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _normalize_asyncpg_ssl_query(database_url: str) -> str:
    parsed = urlsplit(database_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if not query:
        return database_url
    has_ssl = any(key == "ssl" for key, _ in query)
    normalized_query = [(key, value) for key, value in query if key != "sslmode"]
    if not has_ssl:
        normalized_query.extend(("ssl", value) for key, value in query if key == "sslmode")
    return urlunsplit((*parsed[:3], urlencode(normalized_query), parsed.fragment))


def _is_secure_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )
