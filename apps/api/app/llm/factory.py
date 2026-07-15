from __future__ import annotations

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.fallback import FallbackLLMProvider
from app.llm.groq import GroqProvider
from app.llm.mock import MockLLMProvider
from app.llm.ollama import OllamaProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    primary = _create_provider(settings.llm_provider, settings=settings)
    fallback_name = settings.llm_fallback_provider
    fallback_model = _normalized_optional(settings.llm_fallback_model)
    if fallback_name is None and fallback_model is not None:
        fallback_name = settings.llm_provider
    if fallback_name is None:
        return primary
    fallback = _create_provider(
        fallback_name,
        settings=settings,
        model_override=fallback_model,
    )
    if fallback.name == primary.name and fallback.model == primary.model:
        return primary
    return FallbackLLMProvider(primary, fallback)


def _create_provider(
    name: str,
    *,
    settings: Settings,
    model_override: str | None = None,
) -> LLMProvider:
    if name == "groq":
        return GroqProvider(
            api_key=settings.groq_signing_key,
            base_url=settings.groq_base_url,
            model=model_override or settings.groq_model,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            retry_base_seconds=settings.llm_retry_base_seconds,
        )
    if name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=model_override or settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return MockLLMProvider()


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
