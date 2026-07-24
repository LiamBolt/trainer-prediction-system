"""Aggregates every version-1 router under a single prefix.

One place that knows the full API surface. A router added to `app/api/v1/` and not
registered here simply does not exist, which is a failure that shows up immediately
rather than subtly.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    allocations,
    audit,
    auth,
    dashboard,
    evaluations,
    notifications,
    predictions,
    programmes,
    reference,
    reports,
    scoring_policy,
    system,
    trainers,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(reference.router)
api_router.include_router(trainers.router)
api_router.include_router(programmes.router)
api_router.include_router(predictions.router)
api_router.include_router(scoring_policy.router)
api_router.include_router(allocations.router)
# §6.3's `/trainers/me/assignments` — handlers live in `allocations.py`, beside the
# approval logic that creates the assignments they answer.
api_router.include_router(allocations.assignments_router)
api_router.include_router(evaluations.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(users.router)
api_router.include_router(users.roles_router)
api_router.include_router(audit.router)
# §6.14's `/system/*`. The root-level liveness and readiness probes are mounted
# separately in `main.py`, unversioned, because a healthcheck should not care.
api_router.include_router(system.system_router)
