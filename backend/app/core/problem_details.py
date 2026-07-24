"""RFC 9457 ``application/problem+json`` rendering and exception handlers (B9).

**One error shape across the whole API**, including validation failures. A client that
must branch on three different error formats will get one of them wrong, and the one
it gets wrong will be the rare path nobody tested.

No stack trace ever reaches a client. Unhandled exceptions return the correlation id
and nothing else; the detail goes to the logs, where it belongs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import TPSError
from app.middleware.correlation import get_correlation_id

logger = logging.getLogger(__name__)

#: Base URI for error type identifiers. These are stable identifiers, not URLs that
#: must resolve — RFC 9457 permits that, and clients branch on the string.
ERROR_TYPE_BASE = "https://tps.upf.go.ug/errors"

PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_response(
    *,
    status_code: int,
    title: str,
    detail: str,
    error_type: str,
    instance: str,
    errors: list[dict[str, str]] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an RFC 9457 problem response.

    Args:
        status_code: HTTP status.
        title: Short, human-readable summary of the error class.
        detail: Explanation of this specific occurrence, written for an officer.
        error_type: Slug appended to :data:`ERROR_TYPE_BASE`.
        instance: The request path.
        errors: Per-field messages for inline form rendering.
        extra: Additional top-level members.

    Returns:
        A JSON response with the problem media type.
    """
    body: dict[str, Any] = {
        "type": f"{ERROR_TYPE_BASE}/{error_type}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "requestId": get_correlation_id(),
    }
    if errors:
        body["errors"] = errors
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_CONTENT_TYPE)


def _field_path(location: tuple[Any, ...]) -> str:
    """Render a Pydantic error location as a client-meaningful field path.

    The frontend renders these against form fields, so the path must be accurate.
    Pydantic prefixes the location with ``body``/``query``/``path``, which is noise to
    a form; everything after it is the field the user actually typed into.

    Args:
        location: Pydantic's ``loc`` tuple.

    Returns:
        A dotted path, e.g. ``"weights.SPECIALIZATION"``.
    """
    parts = [str(part) for part in location if part not in {"body", "query", "path", "header"}]
    return ".".join(parts) if parts else "request"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every exception handler to the application.

    Args:
        app: The FastAPI application.
    """

    @app.exception_handler(TPSError)
    async def handle_domain_error(request: Request, exc: TPSError) -> JSONResponse:
        """Render a domain exception as its mapped status.

        This is the seam that keeps `fastapi` out of the service layer (B7): services
        raise plain Python exceptions, and exactly one place knows about HTTP.
        """
        return problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            error_type=exc.error_type,
            instance=request.url.path,
            errors=exc.errors,
            extra=exc.extra,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Render Pydantic validation failures in the same problem shape.

        FastAPI's default 422 body is a different shape from every other error this
        API returns. Overriding it is what makes B9's "one error shape" true rather
        than aspirational.
        """
        errors = [
            {"field": _field_path(error["loc"]), "message": error["msg"]} for error in exc.errors()
        ]
        summary = errors[0]["message"] if len(errors) == 1 else f"{len(errors)} fields are invalid."
        return problem_response(
            status_code=422,  # UNPROCESSABLE CONTENT — literal avoids the renamed-constant deprecation
            title="Validation failed",
            detail=f"The information supplied could not be accepted. {summary}",
            error_type="validation-failed",
            instance=request.url.path,
            errors=errors,
        )

    @app.exception_handler(PydanticValidationError)
    async def handle_model_validation_error(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        """Render a Pydantic model error raised outside request parsing.

        `RequestValidationError` above covers body, query, and path parsing. It does
        **not** cover a `model_validator` that raises while a dependency object is
        being constructed — `PageParams`' deep-offset guard is exactly that case, and
        without this handler it escaped to a 500. A rule the API deliberately enforces
        must not be reported as the API breaking.
        """
        errors = [
            {"field": _field_path(error["loc"]), "message": error["msg"]} for error in exc.errors()
        ]
        summary = errors[0]["message"] if len(errors) == 1 else f"{len(errors)} values are invalid."
        return problem_response(
            status_code=422,  # UNPROCESSABLE CONTENT — literal avoids the renamed-constant deprecation
            title="Validation failed",
            detail=f"The information supplied could not be accepted. {summary}",
            error_type="validation-failed",
            instance=request.url.path,
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Render framework-raised HTTP errors (404 routing, 405) in problem shape."""
        titles = {
            404: "Not found",
            405: "Method not allowed",
            429: "Too many requests",
        }
        return problem_response(
            status_code=exc.status_code,
            title=titles.get(exc.status_code, "Request failed"),
            detail=str(exc.detail),
            error_type=f"http-{exc.status_code}",
            instance=request.url.path,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """Render an unhandled exception as a bare 500.

        The client gets the correlation id and nothing else. The exception, with its
        traceback, goes to the log where it can be found by that same id. Leaking a
        stack trace tells an attacker the framework, the versions, and the file
        layout, and tells a police officer nothing at all.
        """
        logger.exception(
            "Unhandled exception",
            extra={"path": request.url.path, "correlation_id": get_correlation_id()},
        )
        return problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal server error",
            detail=(
                "Something went wrong on our side. Please try again. If it keeps "
                "happening, quote the reference below when reporting it."
            ),
            error_type="internal-error",
            instance=request.url.path,
        )

    _ = (
        handle_domain_error,
        handle_validation_error,
        handle_http_exception,
        handle_unexpected,
    )  # registered by decorator; bound here only to satisfy linters
