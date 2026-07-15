from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager

import httpx

from app.llm.base import (
    LLMGeneration,
    LLMProviderUnavailable,
    LLMStreamEvent,
    TokenUsage,
)

GROQ_CHAT_PATH = "/chat/completions"
GROQ_MODELS_PATH = "/models"
TRANSIENT_STATUS_CODES = {429, 498, 500, 502, 503, 504}
SAFE_RATE_LIMIT_DETAIL = (
    "The text provider is busy. Your message was saved; retry the reply shortly."
)
SAFE_QUOTA_DETAIL = (
    "The text provider quota is exhausted. Your message was saved; retry after it resets."
)
SAFE_CONTEXT_DETAIL = (
    "This conversation has outgrown the provider context window. Your message was saved."
)
SAFE_AUTH_DETAIL = "The text provider is not configured correctly. Your message was saved."
SAFE_MODEL_DETAIL = "The configured text model is unavailable. Your message was saved."
SAFE_MALFORMED_DETAIL = (
    "The text provider returned an unreadable reply. Your message was saved; retry the reply."
)
SAFE_EMPTY_DETAIL = (
    "The text provider returned no reply. Your message was saved; you can retry the reply."
)
SAFE_REFUSAL_DETAIL = (
    "The text provider could not answer that message. Your message was saved so you can revise it."
)
SAFE_TIMEOUT_DETAIL = "The text provider timed out. Your message was saved; retry the reply."
SAFE_UNAVAILABLE_DETAIL = (
    "The text provider is unavailable. Your message was saved; you can retry the reply."
)


class GroqProvider:
    name = "groq"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        timeout_seconds: float,
        max_retries: int,
        retry_base_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self._client = client

    async def generate(self, prompt: str) -> LLMGeneration:
        payload = self._payload(prompt, stream=False)
        for attempt in range(self.max_retries + 1):
            try:
                async with self._managed_client() as client:
                    response = await client.post(
                        f"{self.base_url}{GROQ_CHAT_PATH}",
                        headers=self._headers(),
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                if response.status_code >= 400:
                    failure = _http_failure(response)
                    if failure.retryable and attempt < self.max_retries:
                        await self._retry_wait(attempt, response)
                        continue
                    raise failure
                return _parse_generation(response)
            except LLMProviderUnavailable:
                raise
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await self._retry_wait(attempt)
                    continue
                raise LLMProviderUnavailable(
                    SAFE_TIMEOUT_DETAIL,
                    failure_type="timeout",
                    retryable=True,
                ) from exc
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    await self._retry_wait(attempt)
                    continue
                raise LLMProviderUnavailable(SAFE_UNAVAILABLE_DETAIL) from exc
        raise LLMProviderUnavailable(SAFE_UNAVAILABLE_DETAIL)

    async def stream(self, prompt: str) -> AsyncIterator[LLMStreamEvent]:
        payload = self._payload(prompt, stream=True)
        for attempt in range(self.max_retries + 1):
            emitted_content = False
            try:
                async with self._managed_client() as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}{GROQ_CHAT_PATH}",
                        headers=self._headers(),
                        json=payload,
                        timeout=self.timeout_seconds,
                    ) as response:
                        if response.status_code >= 400:
                            await response.aread()
                            failure = _http_failure(response)
                            if failure.retryable and attempt < self.max_retries:
                                await self._retry_wait(attempt, response)
                                continue
                            raise failure

                        saw_done = False
                        saw_finish = False
                        refused = False
                        usage = TokenUsage()
                        async for line in response.aiter_lines():
                            stripped = line.strip()
                            if not stripped or stripped.startswith(":"):
                                continue
                            if not stripped.startswith("data:"):
                                raise _malformed_failure()
                            data = stripped.removeprefix("data:").strip()
                            if data == "[DONE]":
                                saw_done = True
                                break
                            event = _parse_stream_event(data, model=self.model)
                            if event.usage != TokenUsage():
                                usage = event.usage
                            if event.content:
                                emitted_content = True
                            if event.finish_reason is not None:
                                saw_finish = True
                                refused = refused or event.finish_reason in {
                                    "content_filter",
                                    "refusal",
                                    "safety",
                                }
                            if (
                                event.content
                                or event.finish_reason is not None
                                or event.usage != TokenUsage()
                            ):
                                yield event

                        if not saw_done:
                            raise _malformed_failure()
                        if not emitted_content:
                            failure_type = "refusal" if refused else "empty_response"
                            detail = SAFE_REFUSAL_DETAIL if refused else SAFE_EMPTY_DETAIL
                            raise LLMProviderUnavailable(
                                detail,
                                failure_type=failure_type,
                                retryable=False,
                            )
                        if not saw_finish and usage != TokenUsage():
                            yield LLMStreamEvent(
                                provider=self.name,
                                model=self.model,
                                finish_reason="stop",
                                usage=usage,
                            )
                        return
            except LLMProviderUnavailable:
                raise
            except httpx.TimeoutException as exc:
                if not emitted_content and attempt < self.max_retries:
                    await self._retry_wait(attempt)
                    continue
                raise LLMProviderUnavailable(
                    SAFE_TIMEOUT_DETAIL,
                    failure_type="timeout",
                    retryable=not emitted_content,
                ) from exc
            except httpx.TransportError as exc:
                if not emitted_content and attempt < self.max_retries:
                    await self._retry_wait(attempt)
                    continue
                raise LLMProviderUnavailable(
                    SAFE_UNAVAILABLE_DETAIL,
                    retryable=not emitted_content,
                ) from exc
        raise LLMProviderUnavailable(SAFE_UNAVAILABLE_DETAIL)

    async def health(self) -> dict[str, str]:
        try:
            async with self._managed_client() as client:
                response = await client.get(
                    f"{self.base_url}{GROQ_MODELS_PATH}",
                    headers=self._headers(),
                    timeout=min(self.timeout_seconds, 8),
                )
            if response.status_code >= 400:
                return self._degraded_health()
            payload = response.json()
            models = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(models, list):
                return self._degraded_health()
            model_ids = {
                item.get("id") for item in models if isinstance(item, dict) and item.get("id")
            }
            if self.model not in model_ids:
                return self._degraded_health()
            return {
                "status": "ok",
                "provider": self.name,
                "model": self.model,
                "configuration": "configured",
                "readiness": "reachable",
            }
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return self._degraded_health()

    def _payload(self, prompt: str, *, stream: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "system", "content": prompt}],
            "temperature": self.temperature,
            "max_completion_tokens": self.max_output_tokens,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _retry_wait(
        self,
        attempt: int,
        response: httpx.Response | None = None,
    ) -> None:
        retry_after = _retry_after_seconds(response)
        delay = retry_after if retry_after is not None else self.retry_base_seconds * (2**attempt)
        await asyncio.sleep(min(max(delay, 0.0), 30.0))

    def _managed_client(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        if self._client is not None:
            return _BorrowedClient(self._client)
        return httpx.AsyncClient()

    def _degraded_health(self) -> dict[str, str]:
        return {
            "status": "degraded",
            "provider": self.name,
            "model": self.model,
            "configuration": "configured",
            "readiness": "degraded",
        }


class _BorrowedClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, *_: object) -> None:
        return None


def _parse_generation(response: httpx.Response) -> LLMGeneration:
    try:
        payload = response.json()
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("missing choices")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("missing message")
        content = message.get("content")
        finish_reason = choice.get("finish_reason")
        if not isinstance(content, str) or not content.strip():
            if finish_reason == "content_filter" or message.get("refusal"):
                raise LLMProviderUnavailable(
                    SAFE_REFUSAL_DETAIL,
                    failure_type="refusal",
                    retryable=False,
                )
            raise LLMProviderUnavailable(
                SAFE_EMPTY_DETAIL,
                failure_type="empty_response",
                retryable=False,
            )
        return LLMGeneration(
            content=content,
            provider="groq",
            model=str(payload.get("model") or "unknown"),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=_parse_usage(payload.get("usage")),
        )
    except LLMProviderUnavailable:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _malformed_failure() from exc


def _parse_stream_event(data: str, *, model: str) -> LLMStreamEvent:
    try:
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("chunk is not an object")
        choices = payload.get("choices")
        usage = _parse_usage(payload.get("usage"))
        if choices == [] and usage != TokenUsage():
            return LLMStreamEvent(provider="groq", model=model, usage=usage)
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("missing stream choice")
        choice = choices[0]
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            raise ValueError("missing stream delta")
        content = delta.get("content")
        refusal = delta.get("refusal")
        if content is not None and not isinstance(content, str):
            raise ValueError("invalid stream content")
        finish_reason = choice.get("finish_reason")
        if refusal and not content:
            finish_reason = "content_filter"
        return LLMStreamEvent(
            content=content or "",
            provider="groq",
            model=str(payload.get("model") or model),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            usage=usage,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _malformed_failure() from exc


def _parse_usage(value: object) -> TokenUsage:
    if not isinstance(value, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=_token_count(value.get("prompt_tokens")),
        output_tokens=_token_count(value.get("completion_tokens")),
        total_tokens=_token_count(value.get("total_tokens")),
    )


def _token_count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _http_failure(response: httpx.Response) -> LLMProviderUnavailable:
    status = response.status_code
    error_message, error_code = _safe_error_classifiers(response)
    normalized = f"{error_code} {error_message}".lower()
    if status in {401, 403}:
        return LLMProviderUnavailable(
            SAFE_AUTH_DETAIL,
            failure_type="authentication",
            retryable=False,
            status_code=status,
        )
    if status == 404:
        return LLMProviderUnavailable(
            SAFE_MODEL_DETAIL,
            failure_type="model_unavailable",
            retryable=False,
            status_code=status,
        )
    if status in {400, 413} and any(
        marker in normalized for marker in ("context", "too large", "too many tokens")
    ):
        return LLMProviderUnavailable(
            SAFE_CONTEXT_DETAIL,
            failure_type="context_overflow",
            retryable=False,
            status_code=status,
        )
    if status == 429:
        quota = any(marker in normalized for marker in ("quota", "billing", "daily limit"))
        return LLMProviderUnavailable(
            SAFE_QUOTA_DETAIL if quota else SAFE_RATE_LIMIT_DETAIL,
            failure_type="quota_exhausted" if quota else "rate_limited",
            retryable=not quota,
            status_code=status,
        )
    return LLMProviderUnavailable(
        SAFE_UNAVAILABLE_DETAIL,
        failure_type="provider_unavailable",
        retryable=status in TRANSIENT_STATUS_CODES,
        status_code=status,
    )


def _safe_error_classifiers(response: httpx.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return "", ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "", ""
    message = error.get("message")
    code = error.get("code") or error.get("type")
    return (
        message if isinstance(message, str) else "",
        code if isinstance(code, str) else "",
    )


def _retry_after_seconds(response: httpx.Response | None) -> float | None:
    if response is None:
        return None
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _malformed_failure() -> LLMProviderUnavailable:
    return LLMProviderUnavailable(
        SAFE_MALFORMED_DETAIL,
        failure_type="malformed_response",
        retryable=False,
    )
