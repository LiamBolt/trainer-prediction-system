"""Trainer routes (§6.3).

**Note on identity.** Self-service routes are `/trainers/me/...` and derive the trainer
from the bearer token. The frontend currently calls `GET /me/trainer?userId=<id>` and
`PATCH /trainers/{id}` for self-update, which take identity from a **client-supplied
parameter** — any authenticated user could read or edit any trainer by changing the
number. That is Broken Object Level Authorization, and it is not reproduced here; the
four affected frontend call sites are corrected in Phase 3 (conflict B1/B2 in
`PROGRESS.md`, ADR-0012).

Both authorisation layers are present on every route that touches a specific record:
`require_roles` for the coarse check, and an ownership check inside the service or via
:func:`require_trainer_self` for the object-level one.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    ClockDep,
    CurrentUser,
    DbSession,
    current_trainer_id,
    require_roles,
    require_trainer_self,
)
from app.core.exceptions import NotFoundError
from app.core.pagination import Page, PageQuery
from app.models.enums import RoleName
from app.models.identity import User
from app.models.trainer import Trainer
from app.repositories.trainer_repo import TrainerRepository
from app.schemas.base import Message
from app.schemas.trainer import (
    AvailabilityUpdate,
    EvaluationSummary,
    QualificationCreate,
    QualificationRead,
    SpecializationCreate,
    SpecializationRead,
    TrainerDetail,
    TrainerEvaluationsResponse,
    TrainerSelfUpdate,
    TrainerSummary,
    UnavailabilityCreate,
    UnavailabilityRead,
)
from app.services.audit_service import AuditService
from app.services.trainer_service import TrainerService

router = APIRouter(prefix="/trainers", tags=["Trainers"])

STAFF = (RoleName.TRAINING_ADMINISTRATOR, RoleName.TRAINING_OFFICER, RoleName.SYSTEM_ADMINISTRATOR)
#: Self-service routes are gated to trainers at the route level, so a non-trainer is
#: refused (403) *before* the request body is parsed — not after, with a 422 that leaks
#: the fact that the role check runs downstream of validation (§7.1, layer 1).
TR = RoleName.TRAINER

#: Sortable columns, allowlisted. `sortBy` is an identifier, not a value, so it can
#: never be parameterised — an allowlist is the only safe way to accept it.
SORTABLE = {
    "fullName": User.full_name,
    "forceNumber": Trainer.force_number,
    "yearsExperience": Trainer.years_experience,
    "availabilityStatus": Trainer.availability_status,
    "profileCompleteness": Trainer.profile_completeness,
}


def get_service(session: DbSession, clock: ClockDep) -> TrainerService:
    """Construct the trainer service for this request."""
    return TrainerService(session, AuditService(session), clock)


ServiceDep = Annotated[TrainerService, Depends(get_service)]


def _mean_of(evaluations: list[EvaluationSummary]) -> Decimal | None:
    """Return the mean rating, in exact decimal arithmetic.

    ``sum(...) / len(...)`` over Decimals with a plain int start value returns
    ``Decimal | float`` to a type checker and can silently produce a float at runtime
    if the list is empty. Ratings are auditable numbers (B10), so the type is pinned.

    Args:
        evaluations: The evaluations to average.

    Returns:
        The mean, or None when there are none.
    """
    if not evaluations:
        return None
    total = sum((e.score_awarded for e in evaluations), start=Decimal("0"))
    return total / Decimal(len(evaluations))


@router.get(
    "",
    summary="Trainer directory",
    description=(
        "Paginated, filterable directory. `search` matches name **or** force number "
        "via trigram indexes, so partial and mid-word matches work.\n\n"
        "Returns a projection rather than full profiles — call `/trainers/{id}` for "
        "credentials and history."
    ),
    response_model=Page[TrainerSummary],
    dependencies=[Depends(require_roles(*STAFF))],
    responses={
        200: {"description": "A page of trainers."},
        403: {"description": "Trainers cannot browse the directory."},
    },
)
async def list_trainers(
    session: DbSession,
    params: PageQuery,
    search: Annotated[str | None, Query(description="Name or force number.")] = None,
    specialization_area_id: Annotated[int | None, Query(alias="specializationAreaId")] = None,
    proficiency_level_id: Annotated[int | None, Query(alias="proficiencyLevelId")] = None,
    station_id: Annotated[int | None, Query(alias="stationId")] = None,
    region_id: Annotated[int | None, Query(alias="regionId")] = None,
    directorate_id: Annotated[int | None, Query(alias="directorateId")] = None,
    availability_status: Annotated[str | None, Query(alias="availabilityStatus")] = None,
    min_experience: Annotated[int | None, Query(alias="minExperience", ge=0)] = None,
    max_experience: Annotated[int | None, Query(alias="maxExperience", le=50)] = None,
) -> Page[TrainerSummary]:
    """Return a page of trainers.

    Args:
        session: Database session.
        params: Pagination and sort.
        search: Free text over name and force number.
        specialization_area_id: Restrict to holders of a discipline.
        proficiency_level_id: Combined with the above.
        station_id: Posting.
        region_id: Region.
        directorate_id: Directorate.
        availability_status: Availability.
        min_experience: Lower bound on years.
        max_experience: Upper bound on years.

    Returns:
        A page of trainer summaries.
    """
    repo = TrainerRepository(session)
    query = repo.apply_directory_filters(
        repo.directory_query(),
        search=search,
        specialization_area_id=specialization_area_id,
        proficiency_level_id=proficiency_level_id,
        station_id=station_id,
        region_id=region_id,
        directorate_id=directorate_id,
        availability_status=availability_status,
        min_experience=min_experience,
        max_experience=max_experience,
    )
    total = await repo.count(query)
    ordering = params.resolve_sort(SORTABLE, User.full_name)
    rows = await session.execute(query.order_by(ordering).offset(params.offset).limit(params.limit))
    return Page[TrainerSummary].build(
        [TrainerSummary.model_validate(r) for r in rows.all()], total=total, params=params
    )


@router.get(
    "/me",
    dependencies=[Depends(require_roles(TR))],
    summary="Your own trainer profile",
    description=(
        "The caller's trainer record, derived from the bearer token. There is no "
        "`userId` parameter by design — identity comes from the token, never from the "
        "request."
    ),
    response_model=TrainerDetail,
    responses={
        200: {"description": "Your profile."},
        403: {"description": "This account has no linked trainer profile."},
    },
)
async def my_profile(user: CurrentUser, service: ServiceDep) -> TrainerDetail:
    """Return the caller's own trainer profile."""
    return await service.get_detail(current_trainer_id(user))


@router.patch(
    "/me",
    dependencies=[Depends(require_roles(TR))],
    summary="Update your own profile",
    description=(
        "FR-02. Rank, station, years of service, contact number, and biography.\n\n"
        "**Rank, station, and contact number cannot be set empty** — a blank value "
        "returns 422 naming the field, rather than storing a blank where a phone "
        "number was."
    ),
    response_model=TrainerDetail,
    responses={
        200: {"description": "Profile updated."},
        403: {"description": "This account has no linked trainer profile."},
        422: {"description": "A required field was blank or out of range."},
    },
)
async def update_my_profile(
    payload: TrainerSelfUpdate, user: CurrentUser, service: ServiceDep
) -> TrainerDetail:
    """Update the caller's own profile (FR-02)."""
    return await service.update_profile(current_trainer_id(user), payload)


@router.patch(
    "/me/availability",
    dependencies=[Depends(require_roles(TR))],
    summary="Change your availability",
    description=(
        "Marking yourself `AVAILABLE` is refused with 409 while you hold a confirmed "
        "allocation for a course that has not yet finished — you cannot be committed "
        "to a course and open for another at the same time."
    ),
    response_model=TrainerDetail,
    responses={
        200: {"description": "Availability updated."},
        409: {"description": "A confirmed allocation is still in progress."},
    },
)
async def update_my_availability(
    payload: AvailabilityUpdate, user: CurrentUser, service: ServiceDep
) -> TrainerDetail:
    """Change the caller's availability."""
    return await service.set_availability(current_trainer_id(user), payload.availability_status)


@router.get(
    "/me/qualifications",
    dependencies=[Depends(require_roles(TR))],
    summary="Your qualifications",
    response_model=list[QualificationRead],
    responses={200: {"description": "Your qualifications, highest first."}},
)
async def my_qualifications(user: CurrentUser, service: ServiceDep) -> list[QualificationRead]:
    """Return the caller's qualifications."""
    return await service.list_qualifications(current_trainer_id(user))


@router.post(
    "/me/qualifications",
    dependencies=[Depends(require_roles(TR))],
    summary="Add a qualification",
    description=(
        "FR-03. **Appends** — it never overwrites an existing entry. A POST that "
        "replaced the list would silently delete a record of a degree still held."
    ),
    response_model=QualificationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Qualification added."},
        404: {"description": "Unknown level or institution."},
        409: {"description": "The year obtained is in the future."},
    },
)
async def add_qualification(
    payload: QualificationCreate, user: CurrentUser, service: ServiceDep
) -> QualificationRead:
    """Append a qualification (FR-03)."""
    return await service.add_qualification(current_trainer_id(user), payload)


@router.delete(
    "/me/qualifications/{qualification_id}",
    dependencies=[Depends(require_roles(TR))],
    summary="Remove a qualification",
    description="Object-level check: 403 if the qualification belongs to another trainer.",
    response_model=Message,
    responses={
        200: {"description": "Removed."},
        403: {"description": "It belongs to another trainer."},
        404: {"description": "No such qualification."},
    },
)
async def delete_qualification(
    qualification_id: int, user: CurrentUser, service: ServiceDep
) -> Message:
    """Remove one of the caller's qualifications."""
    await service.delete_qualification(current_trainer_id(user), qualification_id)
    return Message(message="Qualification removed.")


@router.get(
    "/me/specializations",
    dependencies=[Depends(require_roles(TR))],
    summary="Your specialisations",
    response_model=list[SpecializationRead],
    responses={200: {"description": "Your specialisations, strongest first."}},
)
async def my_specializations(user: CurrentUser, service: ServiceDep) -> list[SpecializationRead]:
    """Return the caller's specialisations."""
    return await service.list_specializations(current_trainer_id(user))


@router.post(
    "/me/specializations",
    dependencies=[Depends(require_roles(TR))],
    summary="Add a specialisation",
    description=(
        "FR-03. `proficiencyLevelId` is **required** — a missing level is a 422, never "
        "a defaulted BASIC, because a defaulted proficiency would feed the scoring "
        "engine a number nobody stated.\n\n"
        "A duplicate discipline returns **409, not a silent update**: quietly "
        "overwriting would let a trainer downgrade their own recorded level with no "
        "trace."
    ),
    response_model=SpecializationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Specialisation added."},
        404: {"description": "Unknown discipline or proficiency level."},
        409: {"description": "That discipline is already recorded."},
        422: {"description": "proficiencyLevelId was missing."},
    },
)
async def add_specialization(
    payload: SpecializationCreate, user: CurrentUser, service: ServiceDep
) -> SpecializationRead:
    """Add a specialisation (FR-03)."""
    return await service.add_specialization(current_trainer_id(user), payload)


@router.delete(
    "/me/specializations/{specialization_id}",
    dependencies=[Depends(require_roles(TR))],
    summary="Remove a specialisation",
    description="Object-level check: 403 if it belongs to another trainer.",
    response_model=Message,
    responses={
        200: {"description": "Removed."},
        403: {"description": "It belongs to another trainer."},
        404: {"description": "No such specialisation."},
    },
)
async def delete_specialization(
    specialization_id: int, user: CurrentUser, service: ServiceDep
) -> Message:
    """Remove one of the caller's specialisations."""
    await service.delete_specialization(current_trainer_id(user), specialization_id)
    return Message(message="Specialisation removed.")


@router.get(
    "/me/unavailability",
    dependencies=[Depends(require_roles(TR))],
    summary="Your declared absences",
    response_model=list[UnavailabilityRead],
    responses={200: {"description": "Absence windows, soonest first."}},
)
async def my_unavailability(user: CurrentUser, service: ServiceDep) -> list[UnavailabilityRead]:
    """Return the caller's absence windows."""
    return await service.list_unavailability(current_trainer_id(user))


@router.post(
    "/me/unavailability",
    dependencies=[Depends(require_roles(TR))],
    summary="Declare an absence",
    description=(
        "Leave, court, deployment, study, or medical. Overlapping windows are refused "
        "with 409 — you cannot be on leave and in court at the same time, and an "
        "overlap would double-count against the availability gate."
    ),
    response_model=UnavailabilityRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Absence recorded."},
        409: {"description": "It overlaps an existing window."},
        422: {"description": "The end date precedes the start date."},
    },
)
async def add_unavailability(
    payload: UnavailabilityCreate, user: CurrentUser, service: ServiceDep
) -> UnavailabilityRead:
    """Declare an absence window."""
    return await service.add_unavailability(current_trainer_id(user), payload)


@router.delete(
    "/me/unavailability/{unavailability_id}",
    dependencies=[Depends(require_roles(TR))],
    summary="Remove a declared absence",
    response_model=Message,
    responses={
        200: {"description": "Removed."},
        403: {"description": "It belongs to another trainer."},
        404: {"description": "No such record."},
    },
)
async def delete_unavailability(
    unavailability_id: int, user: CurrentUser, service: ServiceDep
) -> Message:
    """Remove one of the caller's absence windows."""
    await service.delete_unavailability(current_trainer_id(user), unavailability_id)
    return Message(message="Absence record removed.")


@router.get(
    "/me/performance",
    dependencies=[Depends(require_roles(TR))],
    summary="Your evaluation history",
    description="Every evaluation recorded against you, with the mean.",
    response_model=TrainerEvaluationsResponse,
    responses={200: {"description": "Your evaluation history."}},
)
async def my_performance(user: CurrentUser, service: ServiceDep) -> TrainerEvaluationsResponse:
    """Return the caller's own evaluation history."""
    trainer_id = current_trainer_id(user)
    evaluations = await service.list_evaluations(trainer_id)
    mean = _mean_of(evaluations)
    return TrainerEvaluationsResponse(evaluations=evaluations, mean=mean)


@router.get(
    "/{trainer_id}",
    summary="A trainer's full profile",
    description=(
        "Credentials, declared absences, and evaluation history.\n\n"
        "A Trainer may fetch **only their own** record; staff roles may fetch any. "
        "This is the object-level check that role gating alone cannot express."
    ),
    response_model=TrainerDetail,
    responses={
        200: {"description": "The trainer's profile."},
        403: {"description": "A Trainer requested someone else's record."},
        404: {"description": "No such trainer."},
    },
)
async def get_trainer(trainer_id: int, user: CurrentUser, service: ServiceDep) -> TrainerDetail:
    """Return one trainer's full profile.

    Args:
        trainer_id: Primary key.
        user: The authenticated caller.
        service: Trainer service.

    Returns:
        The full profile.
    """
    require_trainer_self(user, trainer_id)
    return await service.get_detail(trainer_id)


@router.get(
    "/{trainer_id}/evaluations",
    summary="A trainer's evaluation history",
    description=(
        "Also reachable as `/evaluations/trainer/{trainerId}`. This path exists "
        "because the frontend already calls it."
    ),
    response_model=TrainerEvaluationsResponse,
    responses={
        200: {"description": "Evaluation history with its mean."},
        403: {"description": "A Trainer requested someone else's history."},
        404: {"description": "No such trainer."},
    },
)
async def trainer_evaluations(
    trainer_id: int, user: CurrentUser, service: ServiceDep, session: DbSession
) -> TrainerEvaluationsResponse:
    """Return a trainer's evaluation history.

    Args:
        trainer_id: Primary key.
        user: The authenticated caller.
        service: Trainer service.
        session: Database session, used to confirm the trainer exists.

    Returns:
        The history and its mean.

    Raises:
        NotFoundError: If no such trainer exists.
    """
    require_trainer_self(user, trainer_id)
    if await session.get(Trainer, trainer_id) is None:
        raise NotFoundError("That trainer record could not be found.")
    evaluations = await service.list_evaluations(trainer_id)
    mean = _mean_of(evaluations)
    return TrainerEvaluationsResponse(evaluations=evaluations, mean=mean)
