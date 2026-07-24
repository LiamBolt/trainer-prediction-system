"""Application factory, lifespan, middleware, and router registration (§3).

An app **factory** rather than a module-level singleton, so tests can build isolated
instances with their own dependency overrides instead of mutating shared global state.

**Migrations are never run here** (B12). The container starts the API; a human runs
Alembic as an explicit, reviewable deployment step. Auto-migrating on startup means a
rolling deployment can run two schema versions concurrently, and a crash-looping
container can apply a half-finished migration repeatedly.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.router import api_router
from app.api.v1 import system as system_routes
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.problem_details import problem_response, register_exception_handlers
from app.core.rate_limit import limiter
from app.db.session import engine
from app.middleware.audit_context import AuditContextMiddleware
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware

logger = structlog.get_logger(__name__)

API_DESCRIPTION = """
The **Trainer Prediction System** ranks Uganda Police Force trainers against training
programme requirements and produces an auditable allocation record.

### What this system is

A **decision support system** using deterministic weighted multi-criteria decision
analysis. Five criteria — specialisation match, proven performance, years of service,
qualification, and availability — are normalised to a common 0–100 scale, weighted by a
policy an administrator controls, and summed.

It is **not** machine learning. There is no trained model, no probability, and no
prediction of future events in the statistical sense. Every score decomposes into
per-criterion contributions that a human can read and defend, which is precisely what a
learned ranker could not provide. See `docs/ALGORITHMS.md` for the full reasoning,
including the alternatives that were considered and rejected.

### Reading the numbers

- **`predictionScore`** — a 0–100 weighted total. Comparable *within* one prediction
  run; not meaningful across runs with different weights.
- **`confidenceLevel`** — how much the system **knows about this trainer**, not how
  likely they are to succeed. A trainer with no evaluation history scores LOW
  confidence however strong their qualifications. This is the most misread number in
  the interface.

### Authentication

Sign in at `POST /api/v1/auth/login` to receive a bearer access token (15 minutes) and
a refresh token (7 days). Send the access token as `Authorization: Bearer <token>`.
Rotate at `POST /api/v1/auth/refresh` before expiry.

### Errors

Every error — including validation failures — is
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `application/problem+json`, carrying
a `requestId` that matches the `X-Request-ID` response header. Quote it when reporting
a problem.
"""

OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "Authentication",
        "description": (
            "Sign-in, token rotation, and the current user. Three consecutive failed "
            "sign-ins lock an account for fifteen minutes (FR-01)."
        ),
    },
    {
        "name": "System",
        "description": (
            "Liveness, readiness, and build information. `live` asks whether the "
            "process is running; `ready` asks whether it can serve traffic. They are "
            "different questions and the container healthcheck uses `ready`."
        ),
    },
]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    On startup, verify the database is actually reachable and say something useful if
    it is not. The single most likely failure in this deployment is the container being
    unable to reach PostgreSQL on the host, and a generic connection error sends people
    looking in the wrong place — so the message names the cause.

    Startup does **not** abort on a failed check. The process stays up and `/health/ready`
    reports 503, which is what lets an operator read the diagnosis instead of watching a
    container crash-loop with the log scrolling past.

    Args:
        app: The application being started.

    Yields:
        None, for the lifetime of the application.
    """
    settings = get_settings()
    logger.info(
        "application_starting",
        version=settings.app_version,
        environment=settings.environment,
        database_host=settings.postgres_host,
    )

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("database_reachable", host=settings.postgres_host)
    except Exception as exc:  # report and keep serving; see the docstring
        logger.error(
            "database_unreachable",
            host=settings.postgres_host,
            port=settings.postgres_port,
            error=type(exc).__name__,
            remedy=(
                "The API is running but cannot reach PostgreSQL. From inside a "
                "container on Linux, 'host.docker.internal' resolves only when Compose "
                "supplies extra_hosts: ['host.docker.internal:host-gateway']. "
                "PostgreSQL must also listen on the Docker bridge (listen_addresses) "
                "and permit 172.16.0.0/12 in pg_hba.conf. See §3.3 of "
                "02-DATABASE-PROMPT.md. Diagnose with: docker compose exec backend "
                'python -c "import socket; '
                "print(socket.gethostbyname('host.docker.internal'))\""
            ),
        )

    if settings.jwt_secret_key.startswith("development-only"):
        logger.warning(
            "insecure_jwt_secret",
            remedy="Set JWT_SECRET_KEY in .env. Generate one with: openssl rand -hex 32",
        )

    yield

    logger.info("application_stopping")
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Optional settings override, for tests.

    Returns:
        The configured application.
    """
    config = settings or get_settings()
    configure_logging(config)

    app = FastAPI(
        title="Trainer Prediction System API",
        version=config.app_version,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": "Uganda Police Force — Directorate of Human Resource Development",
            "email": "ict@upf.go.ug",
        },
        license_info={"name": "Restricted — Uganda Police Force internal use"},
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # The limiter is module-level in `app.core.rate_limit` so route decorators can
    # reference it at import time; slowapi's handler looks for it on `app.state`.
    app.state.limiter = limiter

    # Middleware executes outermost-first on the way in and reverses on the way out,
    # and Starlette applies them in reverse registration order — so the last one added
    # is the outermost. Registered here bottom-up to give the order in §3:
    # CORS → correlation → logging → audit context → gzip.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        # Credentials with a wildcard origin is forbidden by the CORS specification and
        # rejected by browsers; the allowlist is explicit and comes from settings.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
    )

    register_exception_handlers(app)

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> Any:
        """Render a rate-limit rejection in the same problem shape as every error."""
        return problem_response(
            status_code=429,
            title="Too many requests",
            detail=("Too many attempts from this address. Please wait a moment and try again."),
            error_type="rate-limited",
            instance=request.url.path,
            extra={"limit": str(exc.detail)},
        )

    _ = handle_rate_limit

    app.include_router(system_routes.router)
    app.include_router(api_router)

    return app


app = create_app()
