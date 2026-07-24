"""Allocation routes (§6.7) and a trainer's own assignments (§6.3).

Two routers live here because one service owns both sides of the same decision: the
Administrator approving, and the trainer answering. Splitting them across modules would
put the accept/decline preconditions a long way from the approval that created them.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from app.api.deps import (
    ClockDep,
    CurrentUser,
    DbSession,
    current_trainer_id,
    require_roles,
    require_trainer_self,
)
from app.core.pagination import Page, PageQuery
from app.models.allocation import Allocation
from app.models.enums import RoleName
from app.schemas.allocation import (
    AllocationListItem,
    ApproveAllocationInput,
    AssignmentsResponse,
    DeclineInput,
    PromoteNextResponse,
    WithdrawInput,
)
from app.services.allocation_service import AllocationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService, dispatch

router = APIRouter(prefix="/allocations", tags=["Allocations"])

#: §6.3 puts a trainer's assignments under `/trainers/me/assignments`. The handlers are
#: here, beside the approval logic that created them.
assignments_router = APIRouter(prefix="/trainers/me/assignments", tags=["Trainer assignments"])

TA = RoleName.TRAINING_ADMINISTRATOR
TO = RoleName.TRAINING_OFFICER
SA = RoleName.SYSTEM_ADMINISTRATOR
TR = RoleName.TRAINER

#: Columns a client may sort the allocation list by. An allowlist, not a passthrough:
#: an unchecked `sortBy` is an ORDER BY injection and a way to sort by a column the
#: caller was never shown.
SORTABLE = {
    "approvalDate": Allocation.approval_date,
    "frozenScore": Allocation.frozen_score,
    "frozenRankPosition": Allocation.frozen_rank_position,
    "status": Allocation.status,
    "registryNumber": Allocation.registry_number,
}


def get_service(session: DbSession, clock: ClockDep) -> AllocationService:
    """Construct the allocation service."""
    return AllocationService(
        session, AuditService(session), NotificationService(session, clock), clock
    )


ServiceDep = Annotated[AllocationService, Depends(get_service)]


def _queue_dispatch(service: AllocationService, background: BackgroundTasks) -> None:
    """Hand queued notifications to a background task (§6.12).

    Dispatch runs after the response is sent. A slow notification must never delay an
    approval — but the *row* was already written inside the approval's transaction, so
    nothing is lost if dispatch fails.

    Args:
        service: The service holding the queued ids.
        background: FastAPI's background task set.
    """
    if service.pending_dispatch:
        background.add_task(dispatch, list(service.pending_dispatch))


@router.get(
    "",
    summary="List allocations",
    description=(
        "Every approved assignment, filterable by status, programme, trainer, "
        "approving officer, and approval date range."
    ),
    response_model=Page[AllocationListItem],
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={200: {"description": "A page of allocations."}},
)
async def list_allocations(
    session: DbSession,
    user: CurrentUser,
    service: ServiceDep,
    params: PageQuery,
    allocation_status: Annotated[
        str | None, Query(alias="status", description="Allocation status.")
    ] = None,
    programme_id: Annotated[int | None, Query(alias="programmeId")] = None,
    trainer_id: Annotated[int | None, Query(alias="trainerId")] = None,
    approved_by: Annotated[int | None, Query(alias="approvedBy")] = None,
    date_from: Annotated[datetime.date | None, Query(alias="from")] = None,
    date_to: Annotated[datetime.date | None, Query(alias="to")] = None,
) -> Page[AllocationListItem]:
    """Return a page of allocations."""
    _ = user
    query = service.apply_filters(
        service.list_query(),
        status=allocation_status,
        programme_id=programme_id,
        trainer_id=trainer_id,
        approved_by=approved_by,
        date_from=date_from,
        date_to=date_to,
    )
    total = await service.count(query)
    ordering = params.resolve_sort(SORTABLE, Allocation.approval_date)
    rows = await session.execute(query.order_by(ordering).offset(params.offset).limit(params.limit))
    return Page[AllocationListItem].build(
        [AllocationListItem.model_validate(row) for row in rows.all()], total=total, params=params
    )


@router.post(
    "",
    summary="Approve an allocation (FR-08)",
    description=(
        "**This is the decision.** BR-02 restricts it to a Training Administrator and "
        "BR-06 requires it to be explicit — there is no auto-approve and no bulk "
        "approve anywhere in this API.\n\n"
        "In one transaction the server verifies the candidate comes from the current "
        "ranking, **re-checks the hard gates against live data** (a trainer may have "
        "become unavailable since the run — 409 if so), freezes the score, breakdown, "
        "rank, weights and rationale, draws a registry number, sets the allocation "
        "`PENDING_TRAINER`, moves the programme to `AWAITING_RESPONSE`, notifies the "
        "trainer, and writes the audit entry (BR-07).\n\n"
        "`weights` and `weightsWereSimulated` in the body are accepted for "
        "compatibility and **ignored** — the frozen weights come from the run itself, "
        "because a receipt whose figures were supplied by the client could be made to "
        "say anything."
    ),
    response_model=AllocationListItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(TA))],
    responses={
        201: {"description": "Approved. The Decision Receipt is the response body."},
        403: {"description": "Only a Training Administrator may approve (BR-02)."},
        404: {"description": "No such candidate."},
        409: {
            "description": (
                "The ranking is superseded, the requirements changed since it was "
                "generated, the programme already has an allocation, or the candidate "
                "no longer passes the gates."
            )
        },
    },
)
async def approve(
    payload: ApproveAllocationInput,
    user: CurrentUser,
    service: ServiceDep,
    response: Response,
    background: BackgroundTasks,
) -> AllocationListItem:
    """Approve an allocation (FR-08, BR-02, BR-06, BR-07)."""
    allocation = await service.approve(
        prediction_id=payload.prediction_id,
        actor_user_id=user.user_id,
        remarks=payload.remarks,
        expected_programme_id=payload.programme_id,
        expected_trainer_id=payload.trainer_id,
    )
    _queue_dispatch(service, background)
    response.headers["Location"] = f"/api/v1/allocations/{allocation.allocation_id}"
    return allocation


@router.get(
    "/{allocation_id}",
    summary="The Decision Receipt",
    description=(
        "The frozen snapshot: score, breakdown, rank and weights **as they stood at "
        "approval**, the rationale the trainer was shown, the approving officer with "
        "their rank, the registry number, the trainer's response, and the linked "
        "evaluation if one exists.\n\n"
        "None of it is recomputed. An evaluation recorded next month changes future "
        "rankings; it must not change the justification for a decision taken today."
    ),
    response_model=AllocationListItem,
    dependencies=[Depends(require_roles(TA, TO, SA, TR))],
    responses={
        200: {"description": "The receipt."},
        403: {"description": "A Trainer may only view their own allocation."},
        404: {"description": "No such allocation."},
    },
)
async def get_allocation(
    allocation_id: int, user: CurrentUser, service: ServiceDep
) -> AllocationListItem:
    """Return one allocation's Decision Receipt.

    The object-level check (B4, layer 2) is what stops a Trainer reading another
    trainer's receipt by changing the number in the URL.
    """
    allocation = await service.get(allocation_id)
    require_trainer_self(user, allocation.trainer_id)
    return allocation


@router.post(
    "/{allocation_id}/promote-next",
    summary="Promote the next-ranked candidate after a decline (FR-08)",
    description=(
        "Takes the next candidate **from the same existing ranking**. FR-08 requires "
        "that a decline does not trigger a new prediction, so `reusedExistingRun` is "
        "always `true` and the frontend states it to the user.\n\n"
        "Candidates passed over on the way — already allocated, or no longer through "
        "the gates — are listed in `skipped` and audited individually as "
        "`CANDIDATE_SKIPPED`."
    ),
    response_model=PromoteNextResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(TA))],
    responses={
        201: {"description": "The next candidate now holds the offer."},
        409: {
            "description": (
                "The allocation was not declined, a replacement was already promoted, "
                "or no remaining candidate meets the requirements."
            )
        },
    },
)
async def promote_next(
    allocation_id: int,
    user: CurrentUser,
    service: ServiceDep,
    background: BackgroundTasks,
) -> PromoteNextResponse:
    """Promote the next-ranked candidate, reusing the existing run."""
    result = await service.promote_next(allocation_id, user.user_id)
    _queue_dispatch(service, background)
    return PromoteNextResponse(
        allocation=result["allocation"],
        reused_existing_run=True,
        run_id=result["run_id"],
        skipped=result["skipped"],
        message=result["message"],
    )


@router.post(
    "/{allocation_id}/mark-conducted",
    summary="Record that the training took place",
    description=(
        "Sets the allocation to `CONDUCTED` and the programme with it. **This is the "
        "gate that unlocks FR-10** — an evaluation cannot be recorded against a course "
        "nobody has confirmed happened."
    ),
    response_model=AllocationListItem,
    dependencies=[Depends(require_roles(TA))],
    responses={
        200: {"description": "Marked conducted."},
        409: {"description": "The trainer has not confirmed this assignment."},
    },
)
async def mark_conducted(
    allocation_id: int, user: CurrentUser, service: ServiceDep
) -> AllocationListItem:
    """Mark an allocation conducted."""
    _ = user
    return await service.mark_conducted(allocation_id)


@router.post(
    "/{allocation_id}/withdraw",
    summary="Withdraw an offer before the trainer answers",
    description=(
        "Requires a reason, which is recorded and sent to the trainer. The programme "
        "returns to `PREDICTED`, so another candidate can be approved from the same "
        "ranking without a re-run."
    ),
    response_model=AllocationListItem,
    dependencies=[Depends(require_roles(TA))],
    responses={
        200: {"description": "Withdrawn."},
        409: {"description": "The trainer has already responded."},
        422: {"description": "No reason was given."},
    },
)
async def withdraw(
    allocation_id: int,
    payload: WithdrawInput,
    user: CurrentUser,
    service: ServiceDep,
    background: BackgroundTasks,
) -> AllocationListItem:
    """Withdraw a pending offer."""
    _ = user
    allocation = await service.withdraw(allocation_id, payload.reason)
    _queue_dispatch(service, background)
    return allocation


# ---------------------------------------------------------------- FR-09 (trainer)


@assignments_router.get(
    "",
    summary="My assignments",
    description=(
        "Pending invitations, confirmed upcoming courses, and past assignments.\n\n"
        "Each pending item carries `frozenRationale` — **the trainer is entitled to see "
        "why they were selected**, not merely that they were."
    ),
    response_model=AssignmentsResponse,
    dependencies=[Depends(require_roles(TR))],
    responses={200: {"description": "The caller's own assignments."}},
)
async def my_assignments(user: CurrentUser, service: ServiceDep) -> AssignmentsResponse:
    """Return the caller's assignments, scoped by the token."""
    grouped = await service.assignments_for(current_trainer_id(user))
    return AssignmentsResponse(
        pending=grouped["pending"],  # type: ignore[arg-type]
        upcoming=grouped["upcoming"],  # type: ignore[arg-type]
        past=grouped["past"],  # type: ignore[arg-type]
    )


@assignments_router.post(
    "/{allocation_id}/accept",
    summary="Accept an assignment (FR-09)",
    description=(
        "Confirms the assignment, records the response time, moves the programme to "
        "`ALLOCATED`, sets the trainer `ASSIGNED` — which caps their AVAILABILITY "
        "score on future runs, so the system stops favouring someone already "
        "committed — and notifies the approving Administrator."
    ),
    response_model=AllocationListItem,
    dependencies=[Depends(require_roles(TR))],
    responses={
        200: {"description": "Confirmed."},
        403: {"description": "That assignment belongs to another trainer."},
        409: {"description": "It is no longer awaiting a response."},
    },
)
async def accept(
    allocation_id: int, user: CurrentUser, service: ServiceDep, background: BackgroundTasks
) -> AllocationListItem:
    """Accept an assignment."""
    allocation = await service.accept(allocation_id, current_trainer_id(user))
    _queue_dispatch(service, background)
    return allocation


@assignments_router.post(
    "/{allocation_id}/decline",
    summary="Decline an assignment (FR-09)",
    description=(
        "**A reason is required** — 422 without one, and a database `CHECK` refuses any "
        "declined row that lacks it. The Administrator is notified with the reason and "
        "the next-ranked candidate's name, and the programme returns to `PREDICTED` so "
        "that candidate can be promoted from the same ranking.\n\n"
        "BR-07: the decision is audited whether it was an approval or a refusal."
    ),
    response_model=AllocationListItem,
    dependencies=[Depends(require_roles(TR))],
    responses={
        200: {"description": "Declined."},
        403: {"description": "That assignment belongs to another trainer."},
        409: {"description": "It is no longer awaiting a response."},
        422: {"description": "No reason was given."},
    },
)
async def decline(
    allocation_id: int,
    payload: DeclineInput,
    user: CurrentUser,
    service: ServiceDep,
    background: BackgroundTasks,
) -> AllocationListItem:
    """Decline an assignment, with a reason."""
    allocation = await service.decline(allocation_id, current_trainer_id(user), payload.reason)
    _queue_dispatch(service, background)
    return allocation


# --- Group A alias (A7) ------------------------------------------------------
# The frontend calls `POST /allocations/{id}/accept` and `/decline`. §6.3 puts them
# under `/trainers/me/assignments/`. Both are served; identity still comes from the
# token, so the alias adds a path, not a vulnerability. Hidden from the schema so the
# documented surface stays single.


@router.post(
    "/{allocation_id}/accept",
    response_model=AllocationListItem,
    include_in_schema=False,
    dependencies=[Depends(require_roles(TR))],
)
async def accept_alias(
    allocation_id: int, user: CurrentUser, service: ServiceDep, background: BackgroundTasks
) -> AllocationListItem:
    """Alias of `POST /trainers/me/assignments/{id}/accept`."""
    return await accept(allocation_id, user, service, background)


@router.post(
    "/{allocation_id}/decline",
    response_model=AllocationListItem,
    include_in_schema=False,
    dependencies=[Depends(require_roles(TR))],
)
async def decline_alias(
    allocation_id: int,
    payload: DeclineInput,
    user: CurrentUser,
    service: ServiceDep,
    background: BackgroundTasks,
) -> AllocationListItem:
    """Alias of `POST /trainers/me/assignments/{id}/decline`."""
    return await decline(allocation_id, payload, user, service, background)
