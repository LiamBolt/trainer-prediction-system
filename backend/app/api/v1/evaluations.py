"""Evaluation routes (FR-10, §6.8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from app.api.deps import (
    ClockDep,
    CurrentUser,
    DbSession,
    require_roles,
    require_trainer_self,
)
from app.models.enums import RoleName
from app.schemas.evaluation import (
    EvaluationInput,
    EvaluationRead,
    EvaluationRecorded,
    EvaluationsResponse,
)
from app.schemas.trainer import EvaluationSummary, TrainerEvaluationsResponse
from app.services.audit_service import AuditService
from app.services.evaluation_service import EvaluationService
from app.services.notification_service import NotificationService, dispatch

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])

TA = RoleName.TRAINING_ADMINISTRATOR
TO = RoleName.TRAINING_OFFICER
SA = RoleName.SYSTEM_ADMINISTRATOR
TR = RoleName.TRAINER


def get_service(session: DbSession, clock: ClockDep) -> EvaluationService:
    """Construct the evaluation service."""
    return EvaluationService(
        session, AuditService(session), NotificationService(session, clock), clock
    )


ServiceDep = Annotated[EvaluationService, Depends(get_service)]


@router.get(
    "",
    summary="Evaluations: outstanding and recorded",
    description=(
        "Two lists. `awaiting` holds allocations at `CONDUCTED` — training delivered, "
        "score not yet recorded. `recorded` holds the evaluations already entered.\n\n"
        "Separating them is the point: the first list is work owed, and a system that "
        "mixes it with completed work hides the backlog."
    ),
    response_model=EvaluationsResponse,
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={200: {"description": "Outstanding and recorded evaluations."}},
)
async def list_evaluations(
    user: CurrentUser,
    service: ServiceDep,
    recorded_limit: Annotated[
        int,
        Query(
            alias="recordedLimit",
            ge=1,
            le=1000,
            description="How many recorded evaluations to return. The backlog is never truncated.",
        ),
    ] = 200,
) -> EvaluationsResponse:
    """Return outstanding and recorded evaluations."""
    _ = user
    return await service.listing(recorded_limit=recorded_limit)


@router.post(
    "",
    summary="Record a performance evaluation (FR-10)",
    description=(
        "**409 unless the allocation is `CONDUCTED`.** The frontend disables the "
        "control and explains why; the API enforces it regardless, because a score "
        "against training nobody confirmed took place is not an evaluation.\n\n"
        "One evaluation per allocation — a `UNIQUE` constraint makes a second attempt a "
        "409, never a silent overwrite.\n\n"
        "The response `message` states the consequence in plain language for the "
        "interface to echo: *\"Recorded. This score now informs future rankings for "
        "IP Mugisha.\"* That is literally true — the PERFORMANCE criterion reads these "
        "rows on every subsequent run."
    ),
    response_model=EvaluationRecorded,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(TA))],
    responses={
        201: {"description": "Recorded."},
        403: {"description": "Only a Training Administrator may record an evaluation."},
        404: {"description": "No such allocation."},
        409: {"description": "The training is not yet conducted, or already evaluated."},
        422: {"description": "Score out of range, or comments shorter than 20 characters."},
    },
)
async def record_evaluation(
    payload: EvaluationInput,
    user: CurrentUser,
    service: ServiceDep,
    response: Response,
    background: BackgroundTasks,
) -> EvaluationRecorded:
    """Record a performance evaluation (FR-10)."""
    evaluation, message = await service.record(payload, user.user_id)
    if service.pending_dispatch:
        background.add_task(dispatch, list(service.pending_dispatch))
    response.headers["Location"] = f"/api/v1/evaluations/{evaluation.evaluation_id}"
    return EvaluationRecorded(evaluation=evaluation, message=message)


@router.get(
    "/trainer/{trainer_id}",
    summary="A trainer's evaluation history",
    description=(
        "Every score awarded to one trainer, newest first, with the arithmetic mean.\n\n"
        "Note that the mean shown here is the **raw** mean. The figure the prediction "
        "engine uses is shrunk towards the service-wide prior, so a trainer with one "
        "5.0 does not outrank one with twelve consistent 4.6s — see `docs/ALGORITHMS.md`."
    ),
    response_model=TrainerEvaluationsResponse,
    dependencies=[Depends(require_roles(TA, TO, SA, TR))],
    responses={
        200: {"description": "The history."},
        403: {"description": "A Trainer may only view their own history."},
    },
)
async def trainer_history(
    trainer_id: int, user: CurrentUser, service: ServiceDep
) -> TrainerEvaluationsResponse:
    """Return one trainer's evaluation history.

    The object-level check (B4, layer 2) is what keeps a Trainer from reading a
    colleague's scores by changing the number in the URL.
    """
    require_trainer_self(user, trainer_id)
    evaluations, mean = await service.for_trainer(trainer_id)
    return TrainerEvaluationsResponse(
        evaluations=[
            EvaluationSummary(
                evaluation_id=e.evaluation_id,
                allocation_id=e.allocation_id,
                trainer_id=e.trainer_id,
                programme_id=e.programme_id,
                programme_title=e.programme_title,
                score_awarded=e.score_awarded,
                evaluator_comments=e.evaluator_comments,
                evaluated_by=e.evaluated_by,
                evaluated_by_name=e.evaluated_by_name,
                evaluation_date=e.evaluation_date,
            )
            for e in evaluations
        ],
        mean=mean,
    )


@router.get(
    "/{evaluation_id}",
    summary="One evaluation",
    response_model=EvaluationRead,
    dependencies=[Depends(require_roles(TA, TO, SA, TR))],
    responses={
        200: {"description": "The evaluation."},
        403: {"description": "A Trainer may only view their own evaluation."},
        404: {"description": "No such evaluation."},
    },
)
async def get_evaluation(
    evaluation_id: int, user: CurrentUser, service: ServiceDep
) -> EvaluationRead:
    """Return one evaluation."""
    evaluation = await service.get(evaluation_id)
    require_trainer_self(user, evaluation.trainer_id)
    return evaluation
