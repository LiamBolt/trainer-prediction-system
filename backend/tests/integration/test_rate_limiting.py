"""Rate limiting (§7.5, NFR-04).

The suite disables the limiter globally — several hundred sign-ins from one address in
under a minute would otherwise trip it and make unrelated tests fail with 429s that look
like authorisation bugs. This module turns it back on deliberately, so the limit is
exercised as configured rather than assumed.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from app.core.rate_limit import client_key, limiter


@pytest.fixture
def rate_limiting_on() -> Iterator[None]:
    """Enable the limiter and clear its counters for one test."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()
    limiter.enabled = False


async def test_repeated_sign_in_attempts_are_throttled(
    client: httpx.AsyncClient, rate_limiting_on: None
) -> None:
    """FR-01's lockout protects one account; this protects the service.

    An attacker spraying one password across many usernames never trips a per-account
    counter — every attempt is the first failure for a different account. The address
    limit is what catches that shape of attack.
    """
    statuses = []
    for index in range(12):
        response = await client.post(
            "/auth/login",
            json={"username": f"nobody{index}", "password": "wrong-password"},
        )
        statuses.append(response.status_code)

    assert 429 in statuses, f"the limiter never fired: {statuses}"
    assert statuses[0] == 401, "the first attempt should be answered normally"
    # Once it fires it stays fired for the window.
    first_429 = statuses.index(429)
    assert all(code == 429 for code in statuses[first_429:])


async def test_the_throttle_uses_the_standard_error_shape(
    client: httpx.AsyncClient, rate_limiting_on: None
) -> None:
    """B9: one error shape across the whole API, including this one."""
    response = None
    for _ in range(15):
        response = await client.post(
            "/auth/login", json={"username": "nobody", "password": "wrong"}
        )
        if response.status_code == 429:
            break

    assert response is not None
    assert response.status_code == 429
    body = response.json()
    assert body["type"].endswith("/rate-limited")
    assert body["status"] == 429
    assert body["title"] == "Too many requests"
    assert "requestId" in body
    assert "limit" in body
    # Written for an officer, not a developer.
    assert "wait a moment" in body["detail"]


def test_the_limit_key_prefers_the_forwarded_address() -> None:
    """Behind a proxy, the socket address is the proxy's.

    Without this, every user in a district shares one counter and the first burst locks
    out the lot. The header is client-controllable, which is acceptable *here* and would
    not be for authorisation: the worst case is an attacker minting fresh buckets, which
    is no worse than having no limit at all.
    """
    from starlette.datastructures import Headers
    from starlette.requests import Request

    def build(headers: dict[str, str], client_host: str) -> Request:
        scope = {
            "type": "http",
            "headers": Headers(headers).raw,
            "client": (client_host, 12345),
        }
        return Request(scope)

    assert client_key(build({"X-Forwarded-For": "41.210.1.9"}, "10.0.0.2")) == "41.210.1.9"
    # Left-most entry is the original client.
    assert (
        client_key(build({"X-Forwarded-For": "41.210.1.9, 10.0.0.1"}, "10.0.0.2"))
        == "41.210.1.9"
    )
    # No header: fall back to the socket.
    assert client_key(build({}, "10.0.0.2")) == "10.0.0.2"
