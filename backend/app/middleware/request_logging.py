"""Structured request logging with duration.

Logs events with **fields**, not interpolated prose. `"request completed" path=/x
status=200 duration_ms=42` can be queried; `"GET /x returned 200 in 42ms"` can only be
grepped, and only if you guess the wording.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.audit_context import get_audit_context
from app.middleware.correlation import get_correlation_id

logger = structlog.get_logger(__name__)

#: Paths that would otherwise flood the log. Health checks run every 30 seconds.
QUIET_PATHS = frozenset({"/health/live", "/health/ready", "/metrics"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emits one structured line per request, with its duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Time the request and log its outcome."""
        started = time.perf_counter()
        quiet = request.url.path in QUIET_PATHS

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                correlation_id=get_correlation_id(),
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        if not quiet or response.status_code >= 400:
            context = get_audit_context()
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
                user_id=context.actor_user_id,
                correlation_id=get_correlation_id(),
            )
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response
