"""Correlation-ID middleware.

Generates or accepts an ``X-Request-ID``, stores it in a :mod:`contextvars` variable
for the life of the request, and returns it on the response.

A ``contextvar`` rather than threading the id through every function signature: it is
the async-safe analogue of thread-local storage, and it means a log line emitted six
layers deep inside the prediction engine still carries the id without the engine
knowing anything about HTTP.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    """Return the current request's correlation id, or ``"-"`` outside a request."""
    return _correlation_id.get()


def set_correlation_id(value: str) -> None:
    """Set the correlation id for the current context."""
    _correlation_id.set(value)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns every request a traceable identifier.

    An inbound ``X-Request-ID`` is honoured so a trace survives a proxy hop; otherwise
    one is generated. Returning it lets a user quote a single reference in a bug
    report that maps directly to a log query.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Attach a correlation id to the request context and the response."""
        incoming = request.headers.get(REQUEST_ID_HEADER)
        correlation_id = incoming if incoming else uuid.uuid4().hex
        set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = correlation_id
        return response
