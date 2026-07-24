"""Rate limiting (§7.5, NFR-04).

Two endpoints are limited, and only two, because a limit that fires on ordinary work
trains people to retry rather than to stop:

- **`POST /auth/login`** — the only unauthenticated endpoint that accepts a guess.
  FR-01's five-attempt lockout protects one *account*; this protects the *service* from
  an attacker spraying one password across many usernames, which never trips a per-
  account counter.
- **`POST /predictions/simulate`** — the Weight Studio's sliders. The frontend debounces
  them, but a debounce is a client-side courtesy and this endpoint runs the engine over
  the whole trainer pool.

Keyed on the client address. Behind a reverse proxy that must be the *forwarded*
address, or every request appears to come from the proxy and one user's burst locks out
a district — see :func:`client_key`.

**State is in-process.** With one API container that is correct. With several, each
holds its own counter and the effective limit multiplies by the number of replicas.
That is a deliberate, documented limitation rather than an oversight: the fix is a
shared Redis backend, and adding Redis for this alone, before it is needed, is the
larger mistake. Recorded in ADR-0013.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings


def client_key(request: Request) -> str:
    """Return the key a limit is counted against.

    Prefers the left-most address in ``X-Forwarded-For``, which is the original client
    when the header is set by a trusted proxy. Falls back to the socket address.

    The header is client-controllable in principle. That is acceptable here and would
    not be for authorisation: the worst case is an attacker giving themselves a fresh
    bucket per forged address, which is no worse than having no limit — while ignoring
    the header entirely would put every user in a district behind one shared counter,
    which breaks the system for legitimate users on the first burst.

    Args:
        request: The incoming request.

    Returns:
        A stable key for this client.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


#: The application-wide limiter. Module-level so route decorators can reference it at
#: import time; `create_app()` attaches it to `app.state`, which is where slowapi's
#: exception handler looks for it.
limiter = Limiter(key_func=client_key, default_limits=[])


def login_limit() -> str:
    """Return the configured limit for sign-in attempts."""
    return get_settings().rate_limit_login


def simulate_limit() -> str:
    """Return the configured limit for Weight Studio simulations."""
    return get_settings().rate_limit_simulate
