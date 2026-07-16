from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.llm.base import LLMGeneration, LLMProviderUnavailable, LLMStreamEvent, TokenUsage

OLLAMA_UNAVAILABLE = "Ollama provider is unavailable or returned an invalid response."


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def generate(self, prompt: str) -> LLMGeneration:
        try:
            async with self._managed_client() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                text = payload.get("response")
                if not isinstance(text, str):
                    raise ValueError("Ollama response did not include text.")
                return LLMGeneration(
                    content=text,
                    provider=self.name,
                    model=str(payload.get("model") or self.model),
                    finish_reason=str(payload.get("done_reason") or "stop"),
                    usage=_ollama_usage(payload),
                )
        except httpx.TimeoutException as exc:
            raise LLMProviderUnavailable(
                "The local text provider timed out. Your message was saved; retry the reply.",
                failure_type="timeout",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMProviderUnavailable(OLLAMA_UNAVAILABLE) from exc

    async def generate_structured(
        self,
        prompt: str,
        *,
        schema_name: str,
        schema: dict[str, object],
        max_output_tokens: int,
    ) -> LLMGeneration:
        del prompt, schema_name, schema, max_output_tokens
        raise LLMProviderUnavailable(
            "The configured provider does not support strict structured cognition.",
            failure_type="model_unavailable",
            retryable=False,
        )

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        try:
            async with self._managed_client() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": True},
                    timeout=self.timeout_seconds,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        payload = json.loads(line)
                        chunk = payload.get("response")
                        done = payload.get("done") is True
                        if isinstance(chunk, str) and (chunk or done):
                            yield LLMStreamEvent(
                                content=chunk,
                                provider=self.name,
                                model=str(payload.get("model") or self.model),
                                finish_reason=(
                                    str(payload.get("done_reason") or "stop") if done else None
                                ),
                                usage=_ollama_usage(payload) if done else TokenUsage(),
                            )
                        if done:
                            break
        except httpx.TimeoutException as exc:
            raise LLMProviderUnavailable(
                "The local text provider timed out. Your message was saved; retry the reply.",
                failure_type="timeout",
            ) from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LLMProviderUnavailable(OLLAMA_UNAVAILABLE) from exc

    async def health(self) -> dict[str, str]:
        try:
            async with self._managed_client() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5)
                if response.status_code >= 400:
                    return {
                        "status": "degraded",
                        "provider": self.name,
                        "model": self.model,
                        "configuration": "configured",
                        "readiness": "degraded",
                    }
                return {
                    "status": "ok",
                    "provider": self.name,
                    "model": self.model,
                    "configuration": "configured",
                    "readiness": "reachable",
                }
        except httpx.HTTPError:
            return {
                "status": "degraded",
                "provider": self.name,
                "model": self.model,
                "configuration": "configured",
                "readiness": "degraded",
            }

    def _managed_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return _BorrowedClient(self._client)
        return httpx.AsyncClient()


class _BorrowedClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, *_: object) -> None:
        return None


def _ollama_usage(payload: dict) -> TokenUsage:
    return TokenUsage(
        input_tokens=_non_negative_int(payload.get("prompt_eval_count")),
        output_tokens=_non_negative_int(payload.get("eval_count")),
        total_tokens=_sum_optional_tokens(
            payload.get("prompt_eval_count"), payload.get("eval_count")
        ),
    )


def _non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _sum_optional_tokens(left: object, right: object) -> int | None:
    left_value = _non_negative_int(left)
    right_value = _non_negative_int(right)
    if left_value is None and right_value is None:
        return None
    return (left_value or 0) + (right_value or 0)
