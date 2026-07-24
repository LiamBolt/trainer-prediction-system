"""Audit-context middleware.

Captures the actor, IP address, and user agent into a request-scoped contextvar so
:class:`~app.services.audit_service.AuditService` can read them without every service
method taking an ``actor`` parameter it does not otherwise care about (§7.2).

Passing the actor explicitly through five call layers is how audit parameters get
dropped on the one path nobody tested — and a missing audit entry on a rare path is
exactly the entry an investigation later needs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Who is acting, and from where.

    Attributes:
        actor_user_id: The authenticated user, or None before authentication (a
            failed sign-in has no known actor).
        actor_role: Their role at the time of the action. Recorded because roles
            change and an audit entry must state the authority under which an action
            was taken, not the authority its actor holds today.
        ip_address: Client IP, honouring ``X-Forwarded-For`` when behind a proxy.
        user_agent: Client user agent, truncated to the column width.
    """

    actor_user_id: int | None = None
    actor_role: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


#: Default is None rather than an ``AuditContext()`` instance. The dataclass is
#: frozen and therefore safe to share, but a mutable default on a ContextVar is a
#: trap worth not modelling — the accessor materialises an empty context instead.
_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def get_audit_context() -> AuditContext:
    """Return the current request's audit context, or an empty one outside a request."""
    return _audit_context.get() or AuditContext()


def set_audit_actor(user_id: int | None, role: str | None) -> None:
    """Record the authenticated actor once authentication has resolved.

    Called from the ``CurrentUser`` dependency rather than the middleware, because the
    middleware runs before the token has been decoded.

    Args:
        user_id: The authenticated user's id.
        role: Their role name.
    """
    current = get_audit_context()
    _audit_context.set(
        AuditContext(
            actor_user_id=user_id,
            actor_role=role,
            ip_address=current.ip_address,
            user_agent=current.user_agent,
        )
    )


class AuditContextMiddleware(BaseHTTPMiddleware):
    """Populates the request's audit context with network-level facts."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Record the client address and user agent for the duration of the request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Left-most entry is the original client; the rest are proxies.
            ip_address = forwarded.split(",")[0].strip()
        elif request.client is not None:
            ip_address = request.client.host
        else:
            ip_address = None

        _audit_context.set(
            AuditContext(
                actor_user_id=None,
                actor_role=None,
                ip_address=ip_address,
                user_agent=(request.headers.get("User-Agent") or "")[:255] or None,
            )
        )
        return await call_next(request)
