"""Training programme routes (§6.4)."""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep, require_roles
from app.core.pagination import Page, PageQuery
from app.models.enums import RoleName
from app.models.programme import TrainingProgramme
from app.schemas.base import Message
from app.schemas.prediction import PredictionRunRead
from app.schemas.programme import (
    EligibilityPreviewResponse,
    ProgrammeCreate,
    ProgrammeDetail,
    ProgrammeSummary,
    ProgrammeUpdate,
    RequirementsInput,
)
from app.services.audit_service import AuditService
from app.services.prediction_service import PredictionService
from app.services.programme_service import ProgrammeService

router = APIRouter(prefix="/programmes", tags=["Training programmes"])

TA = RoleName.TRAINING_ADMINISTRATOR
TO = RoleName.TRAINING_OFFICER
SA = RoleName.SYSTEM_ADMINISTRATOR

SORTABLE = {
    "title": TrainingProgramme.title,
    "startDate": TrainingProgramme.start_date,
    "endDate": TrainingProgramme.end_date,
    "status": TrainingProgramme.status,
    "createdAt": TrainingProgramme.created_at,
    "registryNumber": TrainingProgramme.registry_number,
}


def get_service(session: DbSession, clock: ClockDep) -> ProgrammeService:
    """Construct the programme service."""
    return ProgrammeService(session, AuditService(session), clock)


def get_prediction_service(
    session: DbSession, clock: ClockDep, settings: SettingsDep
) -> PredictionService:
    """Construct the prediction service."""
    return PredictionService(session, AuditService(session), clock, settings)


ServiceDep = Annotated[ProgrammeService, Depends(get_service)]
PredictionDep = Annotated[PredictionService, Depends(get_prediction_service)]


@router.get(
    "",
    summary="List training programmes",
    description=(
        "Paginated and filterable. Search matches title **or** registry number.\n\n"
        "The list is **not scoped by creator** — officers see all programmes, because "
        "training is coordinated across a directorate rather than owned by whoever "
        "typed the request."
    ),
    response_model=Page[ProgrammeSummary],
    responses={200: {"description": "A page of programmes."}},
)
async def list_programmes(
    session: DbSession,
    service: ServiceDep,
    user: CurrentUser,
    params: PageQuery,
    search: Annotated[str | None, Query(description="Title or registry number.")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    category_id: Annotated[int | None, Query(alias="categoryId")] = None,
    specialization_area_id: Annotated[int | None, Query(alias="specializationAreaId")] = None,
    created_by: Annotated[int | None, Query(alias="createdBy")] = None,
    date_from: Annotated[datetime.date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[datetime.date | None, Query(alias="dateTo")] = None,
) -> Page[ProgrammeSummary]:
    """Return a page of programmes."""
    _ = user
    query = service.apply_filters(
        service.list_query(),
        search=search,
        status=status_filter,
        category_id=category_id,
        specialization_area_id=specialization_area_id,
        created_by=created_by,
        date_from=date_from,
        date_to=date_to,
    )
    total = await service.count(query)
    ordering = params.resolve_sort(SORTABLE, TrainingProgramme.start_date)
    rows = await session.execute(query.order_by(ordering).offset(params.offset).limit(params.limit))
    return Page[ProgrammeSummary].build(
        [ProgrammeSummary.model_validate(r) for r in rows.all()], total=total, params=params
    )


@router.post(
    "",
    summary="Raise a training request",
    description=(
        "FR-04. Creates a programme at `DRAFT` with a generated registry number.\n\n"
        "Requirements are **not** accepted here — FR-05 defines them separately via "
        "`PUT /programmes/{id}/requirements`. Keeping the two apart is what makes the "
        "`DRAFT` → `REQUIREMENTS_SET` transition a real event."
    ),
    response_model=ProgrammeSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(TO, TA))],
    responses={
        201: {"description": "Programme created."},
        403: {"description": "Only officers and administrators may raise requests."},
        404: {"description": "Unknown category or venue."},
    },
)
async def create_programme(
    payload: ProgrammeCreate, user: CurrentUser, service: ServiceDep, response: Response
) -> ProgrammeSummary:
    """Raise a training request (FR-04)."""
    created = await service.create(payload, user.user_id)
    response.headers["Location"] = f"/api/v1/programmes/{created.programme_id}"
    return created


@router.get(
    "/{programme_id}",
    summary="Programme detail",
    description="With its lifecycle timeline, latest prediction run, and allocation count.",
    response_model=ProgrammeDetail,
    responses={200: {"description": "The programme."}, 404: {"description": "No such programme."}},
)
async def get_programme(
    programme_id: int, user: CurrentUser, service: ServiceDep
) -> ProgrammeDetail:
    """Return one programme with its timeline."""
    _ = user
    return await service.get_detail(programme_id)


@router.patch(
    "/{programme_id}",
    summary="Edit a programme",
    description=(
        "Blocked with 409 once the programme is `ALLOCATED` or beyond — a trainer has "
        "accepted a commitment by then, and moving the dates would silently change "
        "what they agreed to."
    ),
    response_model=ProgrammeSummary,
    dependencies=[Depends(require_roles(TO, TA))],
    responses={
        200: {"description": "Updated."},
        409: {"description": "Too far along to edit."},
    },
)
async def update_programme(
    programme_id: int, payload: ProgrammeUpdate, user: CurrentUser, service: ServiceDep
) -> ProgrammeSummary:
    """Edit a programme's particulars."""
    _ = user
    return await service.update(programme_id, payload)


@router.put(
    "/{programme_id}/requirements",
    summary="Define the requirements",
    description=(
        "FR-05. `requiredSpecializationAreaId` is required; minimum experience and "
        "qualification are optional.\n\n"
        "Moves `DRAFT` → `REQUIREMENTS_SET`. **If a ranking already exists**, sets "
        "`requirementsChangedSincePrediction` and audits `REQUIREMENTS_CHANGED` — that "
        "flag raises the amber re-run banner, because the ranking on screen was "
        "computed against different criteria and approving from it would mean "
        "approving against requirements that no longer apply."
    ),
    response_model=ProgrammeSummary,
    dependencies=[Depends(require_roles(TO, TA))],
    responses={
        200: {"description": "Requirements set."},
        404: {"description": "Unknown discipline or qualification level."},
        409: {"description": "The programme is past the point of redefinition."},
    },
)
async def set_requirements(
    programme_id: int, payload: RequirementsInput, user: CurrentUser, service: ServiceDep
) -> ProgrammeSummary:
    """Define a programme's requirements (FR-05)."""
    _ = user
    return await service.set_requirements(programme_id, payload)


@router.post(
    "/{programme_id}/requirements",
    summary="Define the requirements (alias)",
    description="Alias of the `PUT` form, retained because the frontend calls `POST`.",
    response_model=ProgrammeSummary,
    dependencies=[Depends(require_roles(TO, TA))],
    include_in_schema=False,
)
async def set_requirements_post(
    programme_id: int, payload: RequirementsInput, user: CurrentUser, service: ServiceDep
) -> ProgrammeSummary:
    """Alias for the frontend's `POST /requirements`."""
    _ = user
    return await service.set_requirements(programme_id, payload)


@router.get(
    "/{programme_id}/eligibility-preview",
    summary="Live eligibility preview",
    description=(
        'Runs the **gates only** and returns counts: *"142 of 812 trainers meet these '
        'criteria."*\n\n'
        "Cheap by construction — no scoring, no narrative. Its purpose is to let an "
        "officer discover that their criteria are too narrow **before** spending a "
        "prediction run, rather than after staring at a list of three names."
    ),
    response_model=EligibilityPreviewResponse,
    dependencies=[Depends(require_roles(TO, TA))],
    responses={
        200: {"description": "Eligible and total counts."},
        409: {"description": "Requirements are not yet defined (FR-05)."},
    },
)
async def eligibility_preview(
    programme_id: int, user: CurrentUser, prediction: PredictionDep
) -> EligibilityPreviewResponse:
    """Return gate-only eligibility counts."""
    _ = user
    preview = await prediction.preview(programme_id)
    if preview.eligible == 0:
        message = (
            "No trainer meets these criteria. Consider lowering the minimum experience "
            "or qualification."
        )
    elif preview.eligible < 5:
        message = (
            f"Only {preview.eligible} of {preview.total} trainers meet these criteria — "
            "a very narrow field."
        )
    else:
        message = f"{preview.eligible} of {preview.total} trainers meet these criteria."
    return EligibilityPreviewResponse(
        eligible=preview.eligible,
        total=preview.total,
        by_reason=preview.by_reason,
        message=message,
    )


@router.get(
    "/{programme_id}/eligibility",
    summary="Live eligibility preview (alias)",
    description="Alias of `eligibility-preview`, retained because the frontend calls it.",
    response_model=EligibilityPreviewResponse,
    dependencies=[Depends(require_roles(TO, TA))],
    include_in_schema=False,
)
async def eligibility_alias(
    programme_id: int, user: CurrentUser, prediction: PredictionDep
) -> EligibilityPreviewResponse:
    """Alias for the frontend's `/eligibility`."""
    return await eligibility_preview(programme_id, user, prediction)


@router.post(
    "/{programme_id}/predict",
    summary="Generate the ranking",
    description=(
        "FR-06. Runs the engine over every trainer, persists the run, marks prior runs "
        "superseded, clears the re-run flag, and moves the programme to `PREDICTED`.\n\n"
        "**409 if requirements are undefined** — FR-05 forbids proceeding without them, "
        "because the engine would have nothing to match on and would rank the entire "
        "force.\n\n"
        "Prior runs are superseded rather than deleted: what the system recommended, "
        "and when, is part of the audit record."
    ),
    response_model=PredictionRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(TA, TO))],
    responses={
        201: {"description": "Ranking generated and stored."},
        409: {"description": "Requirements are undefined, or no scoring policy is active."},
    },
)
async def predict(
    programme_id: int, user: CurrentUser, prediction: PredictionDep
) -> PredictionRunRead:
    """Generate and persist a ranking (FR-06)."""
    return await prediction.run_and_persist(programme_id, user.user_id)


@router.get(
    "/{programme_id}/prediction",
    summary="The current ranking",
    description=(
        "The latest non-superseded run: ranked candidates with their score breakdowns, "
        "rationales, confidence, and counterfactuals.\n\n"
        "**Always ordered by rank. There is no `sortBy` parameter** — BR-05 fixes the "
        "order, and letting a client re-sort would let the interface present a "
        "different recommendation from the one recorded."
    ),
    response_model=PredictionRunRead,
    dependencies=[Depends(require_roles(TA, TO, SA))],
    responses={
        200: {"description": "The current ranking."},
        404: {"description": "No ranking has been generated yet."},
    },
)
async def current_prediction(
    programme_id: int, user: CurrentUser, prediction: PredictionDep
) -> PredictionRunRead:
    """Return the current ranking for a programme."""
    _ = user
    return await prediction.latest_run_for(programme_id)


@router.delete(
    "/{programme_id}",
    summary="Delete a draft programme",
    description=(
        "Only from `DRAFT` or `REQUIREMENTS_SET`. Anything further along has "
        "allocation history that forms part of the decision record and returns 409 — "
        "cancel it instead, which preserves the record."
    ),
    response_model=Message,
    dependencies=[Depends(require_roles(TA, SA))],
    responses={
        200: {"description": "Deleted."},
        409: {"description": "It has allocation history; cancel instead."},
    },
)
async def delete_programme(programme_id: int, user: CurrentUser, service: ServiceDep) -> Message:
    """Delete a draft programme."""
    _ = user
    await service.delete(programme_id)
    return Message(message="Draft programme deleted.")
