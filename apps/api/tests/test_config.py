from __future__ import annotations

from app.config import Settings


def test_allowed_origins_include_web_origin_and_cors_origins() -> None:
    settings = Settings(
        web_origin="https://sample-3000.app.github.dev/",
        cors_origins="http://localhost:3000, https://sample-3000.app.github.dev/",
    )

    assert settings.allowed_origins == [
        "http://localhost:3000",
        "https://sample-3000.app.github.dev",
    ]
