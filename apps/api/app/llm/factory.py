from __future__ import annotations

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.ollama import OllamaProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    return MockLLMProvider()
