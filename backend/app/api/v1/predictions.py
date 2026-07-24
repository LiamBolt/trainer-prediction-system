"""Prediction run routes (§6.5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep, require_roles
from app.core.exceptions import NotFoundError, ValidationError
from app.core.rate_limit import limiter, simulate_limit
from app.models.enums import RoleName
from app.schemas.prediction import (
    ExclusionGroup,
    PredictionRead,
    PredictionRunRead,
    SimulationRequest,
    SimulationResponse,
)
from app.services.audit_service import AuditService
from app.services.prediction.engine import WeightsError
from app.services.prediction_service import PredictionService
from app.services.scoring_policy_service import ScoringPolicyService

router = APIRouter(prefix="/predictions", tags=["Predictions"])

TA = RoleName.TRAINING_ADMINISTRATOR
TO = RoleName.TRAINING_OFFICER
SA = RoleName.SYSTEM_ADMINISTRATOR


def get_service(session: DbSession, clock: ClockDep, settings: SettingsDep) -> PredictionService:
    """Construct the prediction service."""
    return PredictionService(session, AuditService(session), clock, settings)


ServiceDep = Annotated[PredictionService, Depends(get_service)]


@router.get(
    "/runs/{run_id}",
    summary="A full prediction run",
    description=(
        "Ranked candidates with score breakdowns, rationales, confidence, and "
        "counterfactuals.\n\n"
        "**Always ordered by `rankPosition` ascending. There is no `sortBy` "
        "parameter** — BR-05 fixes the order absolutely."
    ),
    response_model=PredictionRunRead,
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={
        200: {"description": "The run."},
        404: {"description": "No such run."},
    },
)
async def get_run(
    run_id: int,
    user: CurrentUser,
    service: ServiceDep,
    limit: Annotated[int | None, Query(ge=1, le=1000, description="Cap ranked rows.")] = None,
) -> PredictionRunRead:
    """Return one prediction run."""
    _ = user
    return await service.get_run(run_id, limit=limit)


@router.get(
    "/runs/{run_id}/exclusions",
    summary="The Exclusion Ledger",
    description=(
        "Every trainer the gates removed, grouped by reason with counts.\n\n"
        'This is what lets the system answer *"why isn\'t so-and-so on the list?"* '
        "without a phone call. Each entry carries a rule citation — BR-03, BR-04, or "
        "FR-05 — and a sentence written for a non-technical officer."
    ),
    response_model=list[ExclusionGroup],
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={200: {"description": "Exclusions grouped by reason, largest group first."}},
)
async def run_exclusions(
    run_id: int, user: CurrentUser, service: ServiceDep
) -> list[ExclusionGroup]:
    """Return a run's Exclusion Ledger."""
    _ = user
    return await service.exclusions_for(run_id)


@router.get(
    "/runs/{run_id}/predictions/{trainer_id}",
    summary="One candidate's full explanation",
    description="The complete Score Ledger for a single trainer within a run.",
    response_model=PredictionRead,
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={
        200: {"description": "The candidate's breakdown."},
        404: {"description": "That trainer was not ranked in this run."},
    },
)
async def candidate_detail(
    run_id: int, trainer_id: int, user: CurrentUser, service: ServiceDep
) -> PredictionRead:
    """Return one candidate's explanation within a run.

    Raises:
        NotFoundError: If the trainer was not ranked in this run — which usually means
            they were excluded, and the Exclusion Ledger says why.
    """
    _ = user
    run = await service.get_run(run_id)
    for prediction in run.predictions:
        if prediction.trainer_id == trainer_id:
            return prediction
    raise NotFoundError(
        "That trainer was not ranked in this run. They may have been excluded — see "
        "the exclusion ledger for the reason."
    )


@router.post(
    "/simulate",
    summary="Simulate alternative weights (Weight Studio)",
    description=(
        "Runs the **identical engine** with override weights and **persists nothing** "
        "except a `WEIGHTS_SIMULATED` audit entry.\n\n"
        "Weights must total 100 (422 otherwise). The response has the same shape as a "
        "real run, plus `rankDeltas` showing how the top candidates moved against the "
        "stored ranking.\n\n"
        "Same code path as `POST /programmes/{id}/predict` by design — a separate "
        "simulation implementation is how a preview silently diverges from what the "
        "server would actually produce."
    ),
    response_model=SimulationResponse,
    dependencies=[Depends(require_roles(TA))],
    responses={
        200: {"description": "The simulated ranking and rank movements."},
        403: {"description": "Only a Training Administrator may simulate."},
        422: {"description": "The weights do not total 100, or a criterion is unknown."},
    },
)
@limiter.limit(simulate_limit)
async def simulate(
    payload: SimulationRequest,
    user: CurrentUser,
    service: ServiceDep,
    request: Request,
) -> SimulationResponse:
    """Simulate a weighting without persisting it (§5.8).

    Raises:
        ValidationError: If the weights are unusable.
    """
    override = ScoringPolicyService.parse_override(payload.weights)
    try:
        run, deltas = await service.simulate(payload.programme_id, override, user.user_id)
    except WeightsError as exc:
        raise ValidationError(str(exc), errors=[{"field": "weights", "message": str(exc)}]) from exc
    return SimulationResponse(run=run, rank_deltas=deltas, persisted=False)
