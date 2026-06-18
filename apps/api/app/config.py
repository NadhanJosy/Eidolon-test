from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Eidolon"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    cors_origins: str = ""
    enable_debug_routes: bool = False

    database_url: str = "postgresql+asyncpg://eidolon:eidolon_dev_password@localhost:5432/eidolon"

    jwt_secret: str = "change-me-in-real-env"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    llm_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 120.0

    enable_scheduler: bool = False
    scheduler_interval_seconds: int = 60
    scheduler_job_limit: int = 10
    proactive_inactivity_hours: int = 24
    proactive_cooldown_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Settings:
        if self.llm_provider not in {"mock", "ollama"}:
            raise ValueError("LLM_PROVIDER must be either 'mock' or 'ollama'.")
        if (
            self.app_env not in {"development", "testing"}
            and self.jwt_secret == "change-me-in-real-env"
        ):
            raise ValueError(
                "JWT_SECRET must be set to a private value outside development/testing."
            )
        if self.scheduler_interval_seconds < 5:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be at least 5.")
        if self.scheduler_job_limit < 1:
            raise ValueError("SCHEDULER_JOB_LIMIT must be at least 1.")
        if self.proactive_inactivity_hours < 1:
            raise ValueError("PROACTIVE_INACTIVITY_HOURS must be at least 1.")
        if self.proactive_cooldown_hours < 1:
            raise ValueError("PROACTIVE_COOLDOWN_HOURS must be at least 1.")
        if self.jwt_refresh_token_expire_days < 1:
            raise ValueError("JWT_REFRESH_TOKEN_EXPIRE_DAYS must be at least 1.")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")
