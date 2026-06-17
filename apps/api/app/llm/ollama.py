from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx


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

    async def generate(self, prompt: str) -> str:
        async with self._managed_client() as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            text = payload.get("response")
            return text if isinstance(text, str) else ""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
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
                    if isinstance(chunk, str) and chunk:
                        yield chunk
                    if payload.get("done") is True:
                        break

    async def health(self) -> dict[str, str]:
        try:
            async with self._managed_client() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5)
                if response.status_code >= 400:
                    return {"status": "degraded", "provider": self.name}
                return {"status": "ok", "provider": self.name}
        except httpx.HTTPError:
            return {"status": "degraded", "provider": self.name}

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
