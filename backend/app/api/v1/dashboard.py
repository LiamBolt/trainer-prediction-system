"""Dashboard routes (§6.13)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import ClockDep, CurrentUser, DbSession
from app.schemas.dashboard import DashboardData
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_service(session: DbSession, clock: ClockDep) -> DashboardService:
    """Construct the dashboard service."""
    return DashboardService(session, clock)


ServiceDep = Annotated[DashboardService, Depends(get_service)]

_DESCRIPTION = (
    "The panels the caller's role can see, in **one round trip**.\n\n"
    "The four headline figures come back as a single row from one query of scalar "
    "subqueries — read together and shown together, so they cannot disagree by however "
    "long four separate requests would have taken.\n\n"
    "**The role is taken from the token, never from a parameter.** A `role` query "
    "parameter is accepted and ignored: honouring it would let a Trainer request the "
    "Administrator dashboard, which is an authorisation bypass rather than a "
    "convenience. Same for `userId`.\n\n"
    "Panels not belonging to the caller's role are `null`, not empty — the difference "
    "between *no data* and *not your screen*."
)


@router.get(
    "/summary",
    summary="The dashboard for whoever is asking",
    description=_DESCRIPTION,
    response_model=DashboardData,
    response_model_exclude_none=True,
    responses={200: {"description": "The caller's dashboard."}},
)
async def summary(
    user: CurrentUser,
    service: ServiceDep,
    role: Annotated[
        str | None,
        Query(
            deprecated=True,
            description="Ignored. The role comes from the access token.",
        ),
    ] = None,
    user_id: Annotated[
        int | None,
        Query(alias="userId", deprecated=True, description="Ignored. Identity comes from the token."),
    ] = None,
) -> DashboardData:
    """Return the caller's dashboard.

    `role` and `userId` are accepted so the frontend's current call does not 422, and
    are discarded. See the endpoint description.
    """
    _ = (role, user_id)
    return await service.build(user)


# --- Group A alias (A8) ------------------------------------------------------
# The frontend calls `GET /dashboard?role=`. §6.13 specifies `/dashboard/summary`.
# Both are served; the role is derived from the token in either case.


@router.get("", response_model=DashboardData, response_model_exclude_none=True, include_in_schema=False)
async def summary_alias(
    user: CurrentUser,
    service: ServiceDep,
    role: Annotated[str | None, Query()] = None,
    user_id: Annotated[int | None, Query(alias="userId")] = None,
) -> DashboardData:
    """Alias of `GET /dashboard/summary`."""
    return await summary(user, service, role, user_id)
