from __future__ import annotations

from app.core.rate_limit import RateLimiter
from fastapi.testclient import TestClient


def test_auth_rate_limit_returns_429(client: TestClient, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_rate_limit_per_minute", 3)

    for _ in range(3):
        response = client.post(
            "/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
        )
        assert response.status_code == 401

    limited = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1


def test_rate_limiter_memory_fallback() -> None:
    limiter = RateLimiter(redis_url=None)
    assert limiter.hit("key", 2).allowed is True
    assert limiter.hit("key", 2).allowed is True
    denied = limiter.hit("key", 2)
    assert denied.allowed is False
    assert denied.retry_after >= 1

    limiter.reset()
    assert limiter.hit("key", 2).allowed is True
