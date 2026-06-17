from __future__ import annotations

from httpx import AsyncClient


async def register_user(
    client: AsyncClient,
    *,
    email: str = "user@example.com",
    password: str = "good-password",
) -> tuple[str, dict]:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Nadhan"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]


async def auth_headers(client: AsyncClient) -> dict[str, str]:
    token, _ = await register_user(client)
    return {"Authorization": f"Bearer {token}"}
