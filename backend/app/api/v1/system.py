"""Health and version endpoints (§6.14, §3).

``/health/live`` and ``/health/ready`` answer **different questions** and must not be
conflated. Liveness asks "is this process running?" — if it fails, restart the
container. Readiness asks "can it serve traffic?" — if it fails, stop routing to it,
but restarting will not help if the database is what is down.

The container healthcheck uses ``ready``.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select, text

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep, require_roles
from app.models.enums import AccountStatus, AuditAction, DeliveryStatus, RoleName
from app.models.identity import RefreshToken, User
from app.models.prediction import PredictionRun
from app.models.system import AuditLog, Notification
from app.schemas.base import CamelModel
from app.schemas.dashboard import PredictionPerformance, RuntimePoint, SecurityHealth

router = APIRouter(tags=["System"])

#: §6.14's `/system/*` endpoints live under the versioned prefix with the rest of §6.
#: The liveness, readiness and version probes above stay at the root: a container
#: healthcheck and a load balancer should not have to know the API's version.
system_router = APIRouter(prefix="/system", tags=["System"])


class LivenessResponse(CamelModel):
    """Process liveness."""

    status: str = "alive"
    version: str
    timestamp: datetime.datetime


class DependencyStatus(CamelModel):
    """The state of one dependency."""

    name: str
    healthy: bool
    detail: str
    latency_ms: float | None = None


class ReadinessResponse(CamelModel):
    """Readiness, with a per-dependency breakdown."""

    status: str
    version: str
    environment: str
    timestamp: datetime.datetime
    dependencies: list[DependencyStatus]


class VersionResponse(CamelModel):
    """Build identification."""

    version: str
    commit: str
    environment: str


@router.get(
    "/health/live",
    summary="Liveness probe",
    description=(
        "Reports that the process is running and able to serve a request. Does **not** "
        "touch the database — a liveness probe that fails when a dependency is down "
        "causes the orchestrator to restart a container that was working correctly."
    ),
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    responses={200: {"description": "The process is alive."}},
)
async def liveness(settings: SettingsDep, clock: ClockDep) -> LivenessResponse:
    """Return process liveness.

    Args:
        settings: Application settings.
        clock: Injected clock.

    Returns:
        The liveness payload.
    """
    return LivenessResponse(version=settings.app_version, timestamp=clock.now())


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description=(
        "Reports whether the service can handle traffic, by executing `SELECT 1` "
        "against PostgreSQL.\n\n"
        "**If this reports the database as unreachable from inside the container**, the "
        "problem is almost always host networking rather than the application. On "
        'Linux, `host.docker.internal` requires `extra_hosts: ["host.docker.internal:'
        'host-gateway"]` in Compose, PostgreSQL listening on the Docker bridge address, '
        "and a `pg_hba.conf` rule permitting `172.16.0.0/12`. See §3.3 of the database "
        "prompt, and diagnose with:\n\n"
        "```bash\n"
        "docker compose exec backend python -c \\\n"
        "  \"import socket; print(socket.gethostbyname('host.docker.internal'))\"\n"
        "```"
    ),
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Every dependency is reachable."},
        503: {"description": "At least one dependency is unreachable."},
    },
)
async def readiness(
    session: DbSession, settings: SettingsDep, clock: ClockDep, response: Response
) -> ReadinessResponse:
    """Check every dependency and report readiness.

    Returns 503 when any dependency is unhealthy, so an orchestrator stops routing
    traffic here without restarting a process that is not itself at fault.

    Args:
        session: Database session.
        settings: Application settings.
        clock: Injected clock.
        response: Used to set a 503 status without raising.

    Returns:
        The readiness payload.
    """
    dependencies: list[DependencyStatus] = []

    started = clock.now()
    try:
        await session.execute(text("SELECT 1"))
        latency = (clock.now() - started).total_seconds() * 1000
        dependencies.append(
            DependencyStatus(
                name="postgresql",
                healthy=True,
                # The *effective* host, so a managed deploy reports the real database
                # rather than the unused POSTGRES_HOST default ("localhost") — the same
                # confusion the seed banner avoids.
                detail=f"Connected to {settings.effective_db_host} (ssl={settings.use_db_ssl}).",
                latency_ms=round(latency, 2),
            )
        )
    except Exception as exc:  # the probe must report a failure, never propagate one
        dependencies.append(
            DependencyStatus(
                name="postgresql",
                healthy=False,
                detail=(
                    f"Cannot reach PostgreSQL at {settings.effective_db_host}. If this is a "
                    "local container on Linux, host.docker.internal needs a host-gateway "
                    "entry in Compose and PostgreSQL listening on the Docker bridge. If this "
                    "is a managed database, check the connection string and that the pooler "
                    f"host is used. Underlying error: {type(exc).__name__}."
                ),
            )
        )

    healthy = all(dependency.healthy for dependency in dependencies)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if healthy else "not_ready",
        version=settings.app_version,
        environment=settings.environment,
        timestamp=clock.now(),
        dependencies=dependencies,
    )


@router.get(
    "/version",
    summary="Build information",
    description="Version, commit, and environment. Used by the frontend's About panel.",
    response_model=VersionResponse,
    responses={200: {"description": "Build information."}},
)
async def version(settings: SettingsDep) -> VersionResponse:
    """Return build identification.

    Args:
        settings: Application settings.

    Returns:
        Version, commit, and environment.
    """
    return VersionResponse(
        version=settings.app_version,
        commit=settings.git_commit,
        environment=settings.environment,
    )


@system_router.get(
    "/health/prediction-performance",
    summary="Prediction run times against the NFR-01 budget",
    description=(
        "`elapsedMs` for recent runs, with the ten-second NFR-01 threshold and a count "
        "of breaches.\n\n"
        "The chart matters because degradation here is gradual: the pool grows, a "
        "query plan flips, and the run that took 200 ms takes four seconds — still "
        "inside the budget, and still the signal that something changed."
    ),
    response_model=PredictionPerformance,
    dependencies=[Depends(require_roles(RoleName.SYSTEM_ADMINISTRATOR))],
    responses={
        200: {"description": "Run times over the window."},
        403: {"description": "System Administrator only."},
    },
)
async def prediction_performance(
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    clock: ClockDep,
    window_days: Annotated[int, Query(alias="windowDays", ge=1, le=365)] = 30,
) -> PredictionPerformance:
    """Return prediction run times for the System Health chart (§6.14)."""
    _ = user
    since = clock.now() - datetime.timedelta(days=window_days)
    result = await session.execute(
        select(PredictionRun.generated_at, PredictionRun.elapsed_ms)
        .where(PredictionRun.generated_at >= since)
        .order_by(PredictionRun.generated_at)
    )
    rows = result.all()
    runs = [RuntimePoint(date=row.generated_at, ms=row.elapsed_ms) for row in rows]
    durations = [row.elapsed_ms for row in rows]
    threshold = settings.prediction_timeout_ms
    return PredictionPerformance(
        runs=runs,
        threshold_ms=threshold,
        slowest_ms=max(durations, default=0),
        mean_ms=int(sum(durations) / len(durations)) if durations else 0,
        breaches=sum(1 for ms in durations if ms > threshold),
        window_days=window_days,
    )


@system_router.get(
    "/health/security",
    summary="Security figures for the System Health screen",
    description=(
        "Failed sign-ins and unauthorised attempts in the last 24 hours, accounts "
        "currently locked, live sessions, and deactivated accounts.\n\n"
        "`failedNotifications` is included on purpose: a notification that silently "
        "did not arrive is worse than one that visibly did not, so delivery failures "
        "surface here rather than being swallowed."
    ),
    response_model=SecurityHealth,
    dependencies=[Depends(require_roles(RoleName.SYSTEM_ADMINISTRATOR))],
    responses={
        200: {"description": "The security figures."},
        403: {"description": "System Administrator only."},
    },
)
async def security_health(
    session: DbSession, user: CurrentUser, clock: ClockDep
) -> SecurityHealth:
    """Return the security figures (§6.14)."""
    _ = user
    now = clock.now()
    since = now - datetime.timedelta(days=1)

    # One row, five subqueries: these figures are shown together and should be read
    # from the same instant.
    result = await session.execute(
        select(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == AuditAction.LOGIN_FAILED.value,
                AuditLog.created_at >= since,
            )
            .scalar_subquery()
            .label("failed_signins24h"),
            select(func.count())
            .select_from(User)
            .where(User.locked_until.is_not(None), User.locked_until > now)
            .scalar_subquery()
            .label("locked_accounts"),
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == AuditAction.UNAUTHORISED_ATTEMPT.value,
                AuditLog.created_at >= since,
            )
            .scalar_subquery()
            .label("unauthorised_attempts24h"),
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
            .scalar_subquery()
            .label("active_sessions"),
            select(func.count())
            .select_from(User)
            .where(User.account_status == AccountStatus.DEACTIVATED.value)
            .scalar_subquery()
            .label("deactivated_accounts"),
            select(func.count())
            .select_from(Notification)
            .where(Notification.delivery_status == DeliveryStatus.FAILED.value)
            .scalar_subquery()
            .label("failed_notifications"),
        )
    )
    return SecurityHealth.model_validate(result.one())
