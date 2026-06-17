from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Eidolon"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    cors_origins: str = ""

    database_url: str = "postgresql+asyncpg://eidolon:eidolon_dev_password@localhost:5432/eidolon"

    jwt_secret: str = "change-me-in-real-env"
    jwt_access_token_expire_minutes: int = 60

    llm_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 120.0

    enable_scheduler: bool = False
    proactive_inactivity_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        origins = [_normalize_origin(self.web_origin)]
        origins.extend(_normalize_origin(origin) for origin in self.cors_origins.split(","))
        origins = [origin for origin in origins if origin]
        return sorted(set(origins))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")
