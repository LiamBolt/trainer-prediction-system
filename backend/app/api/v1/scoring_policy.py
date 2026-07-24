"""Scoring policy routes (§6.6, NFR-10)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ClockDep, CurrentUser, DbSession, require_roles
from app.models.enums import RoleName
from app.schemas.scoring import ScoringPolicyRead, ScoringPolicyUpdate
from app.services.audit_service import AuditService
from app.services.scoring_policy_service import ScoringPolicyService

router = APIRouter(prefix="/scoring-policy", tags=["Scoring policy"])

TA = RoleName.TRAINING_ADMINISTRATOR
SA = RoleName.SYSTEM_ADMINISTRATOR


def get_service(session: DbSession, clock: ClockDep) -> ScoringPolicyService:
    """Construct the scoring policy service."""
    return ScoringPolicyService(session, AuditService(session), clock)


ServiceDep = Annotated[ScoringPolicyService, Depends(get_service)]


@router.get(
    "",
    summary="The active scoring policy",
    description=(
        "Weights, labels, plain-English descriptions, and who last changed them.\n\n"
        "The descriptions are stored on the row rather than in the frontend, so an "
        "administrator retuning a weight can also correct the sentence that explains "
        "it without waiting for a release."
    ),
    response_model=ScoringPolicyRead,
    dependencies=[Depends(require_roles(TA, SA))],
    responses={
        200: {"description": "The active policy."},
        409: {"description": "No policy is active."},
    },
)
async def get_policy(user: CurrentUser, service: ServiceDep) -> ScoringPolicyRead:
    """Return the active scoring policy."""
    _ = user
    return await service.get_active()


@router.put(
    "",
    summary="Save a new policy version",
    description=(
        "NFR-10. Creates a **new version** and deactivates the previous one — it never "
        "mutates in place.\n\n"
        "That matters because every prediction run stores the weights that produced "
        "it. Editing a policy in place would leave historical rankings explained by "
        "weights that were not in force when they were generated, which is the "
        "difference between an auditable decision and one that merely looked right at "
        "the time.\n\n"
        "All five criteria are required and must total exactly 100."
    ),
    response_model=ScoringPolicyRead,
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {"description": "New version adopted; the previous one is deactivated."},
        403: {"description": "Only a System Administrator may change the weighting."},
        422: {"description": "The weights do not total 100, or a criterion is missing."},
    },
)
async def save_policy(
    payload: ScoringPolicyUpdate, user: CurrentUser, service: ServiceDep
) -> ScoringPolicyRead:
    """Save a new policy version (NFR-10)."""
    return await service.save_new_version(payload, user.user_id)


@router.post(
    "",
    summary="Save a new policy version (alias)",
    description="Alias of the `PUT` form, retained because the frontend calls `POST`.",
    response_model=ScoringPolicyRead,
    dependencies=[Depends(require_roles(SA))],
    include_in_schema=False,
)
async def save_policy_post(
    payload: ScoringPolicyUpdate, user: CurrentUser, service: ServiceDep
) -> ScoringPolicyRead:
    """Alias for the frontend's `POST /scoring-policy`."""
    return await service.save_new_version(payload, user.user_id)


@router.get(
    "/history",
    summary="Every policy version",
    description="With effective dates and authors, so an old ranking can be explained.",
    response_model=list[ScoringPolicyRead],
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "Versions, newest first."}},
)
async def policy_history(user: CurrentUser, service: ServiceDep) -> list[ScoringPolicyRead]:
    """Return every policy version."""
    _ = user
    return await service.history()
