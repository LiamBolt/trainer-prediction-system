"""Training programme lifecycle (FR-04, FR-05).

Imports no `fastapi` (B7).

The status machine is the substance here. A programme moves `DRAFT` →
`REQUIREMENTS_SET` → `PREDICTED` → `AWAITING_RESPONSE` → `ALLOCATED` → `CONDUCTED` →
`EVALUATED`, and each transition has a precondition that exists for a reason rather
than for tidiness — most importantly, nothing may be predicted against a programme
whose requirements are undefined, because the engine would have nothing to match on.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import ConflictError, NotFoundError
from app.models.allocation import Allocation
from app.models.enums import AuditAction, ProgrammeStatus
from app.models.identity import User
from app.models.prediction import PredictionRun
from app.models.programme import TrainingProgramme
from app.models.reference import (
    QualificationLevel,
    SpecializationArea,
    Station,
    TrainingCategory,
)
from app.schemas.programme import (
    ProgrammeCreate,
    ProgrammeDetail,
    ProgrammeRunSummary,
    ProgrammeStatusEvent,
    ProgrammeSummary,
    ProgrammeUpdate,
    RequirementsInput,
)
from app.services.audit_service import AuditService

#: Statuses at which a programme's particulars may still be edited. Beyond these an
#: allocation exists, and changing the dates of a course a trainer has already
#: accepted would rewrite the commitment they agreed to.
EDITABLE_STATUSES = frozenset(
    {ProgrammeStatus.DRAFT, ProgrammeStatus.REQUIREMENTS_SET, ProgrammeStatus.PREDICTED}
)

#: Statuses from which a programme may be deleted outright. Anything further along has
#: allocation history and must be CANCELLED instead, so the record survives.
DELETABLE_STATUSES = frozenset({ProgrammeStatus.DRAFT, ProgrammeStatus.REQUIREMENTS_SET})


class ProgrammeService:
    """Creates and advances training programmes.

    Args:
        session: The request's session.
        audit: Audit service sharing the same transaction (B8).
        clock: Injected clock.
    """

    def __init__(self, session: AsyncSession, audit: AuditService, clock: Clock) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock

    def list_query(self) -> Select[Any]:
        """Build the base projection for the programme list.

        Returns:
            A ``SELECT`` ready for filtering, sorting, and pagination.
        """
        return (
            select(
                TrainingProgramme.programme_id,
                TrainingProgramme.registry_number,
                TrainingProgramme.title,
                TrainingCategory.name.label("category"),
                TrainingProgramme.category_id,
                SpecializationArea.name.label("required_specialization"),
                TrainingProgramme.required_specialization_area_id,
                TrainingProgramme.minimum_experience,
                QualificationLevel.name.label("minimum_qualification"),
                TrainingProgramme.minimum_qualification_level_id,
                TrainingProgramme.start_date,
                TrainingProgramme.end_date,
                Station.name.label("location"),
                TrainingProgramme.station_id,
                TrainingProgramme.expected_participants,
                TrainingProgramme.status,
                TrainingProgramme.created_by_user_id.label("created_by"),
                User.full_name.label("created_by_name"),
                TrainingProgramme.created_at,
                TrainingProgramme.requirements_set_at,
                TrainingProgramme.requirements_changed_since_prediction,
            )
            .join(TrainingCategory, TrainingCategory.category_id == TrainingProgramme.category_id)
            .join(Station, Station.station_id == TrainingProgramme.station_id)
            .join(User, User.user_id == TrainingProgramme.created_by_user_id)
            .outerjoin(
                SpecializationArea,
                SpecializationArea.specialization_area_id
                == TrainingProgramme.required_specialization_area_id,
            )
            .outerjoin(
                QualificationLevel,
                QualificationLevel.level_id == TrainingProgramme.minimum_qualification_level_id,
            )
        )

    @staticmethod
    def apply_filters(
        query: Select[Any],
        *,
        search: str | None = None,
        status: str | None = None,
        category_id: int | None = None,
        specialization_area_id: int | None = None,
        created_by: int | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> Select[Any]:
        """Apply list filters.

        Args:
            query: The base query.
            search: Free text over title and registry number.
            status: Lifecycle status.
            category_id: Delivery category.
            specialization_area_id: Required discipline.
            created_by: Raising officer.
            date_from: Courses starting on or after this date.
            date_to: Courses starting on or before this date.

        Returns:
            The filtered query.
        """
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    TrainingProgramme.title.ilike(pattern),
                    TrainingProgramme.registry_number.ilike(pattern),
                )
            )
        if status:
            query = query.where(TrainingProgramme.status == status)
        if category_id is not None:
            query = query.where(TrainingProgramme.category_id == category_id)
        if specialization_area_id is not None:
            query = query.where(
                TrainingProgramme.required_specialization_area_id == specialization_area_id
            )
        if created_by is not None:
            query = query.where(TrainingProgramme.created_by_user_id == created_by)
        if date_from is not None:
            query = query.where(TrainingProgramme.start_date >= date_from)
        if date_to is not None:
            query = query.where(TrainingProgramme.start_date <= date_to)
        return query

    async def count(self, query: Select[Any]) -> int:
        """Count rows a filtered query would return."""
        result = await self._session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one())

    async def load(self, programme_id: int) -> TrainingProgramme:
        """Load a programme or raise.

        Args:
            programme_id: Primary key.

        Returns:
            The entity.

        Raises:
            NotFoundError: If it does not exist.
        """
        programme = await self._session.get(TrainingProgramme, programme_id)
        if programme is None:
            raise NotFoundError("That training programme could not be found.")
        return programme

    async def get_summary(self, programme_id: int) -> ProgrammeSummary:
        """Return one programme's list projection.

        Args:
            programme_id: Primary key.

        Returns:
            The summary.

        Raises:
            NotFoundError: If it does not exist.
        """
        result = await self._session.execute(
            self.list_query().where(TrainingProgramme.programme_id == programme_id)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("That training programme could not be found.")
        return ProgrammeSummary.model_validate(row)

    async def get_detail(self, programme_id: int) -> ProgrammeDetail:
        """Return a programme with its timeline and latest run.

        Args:
            programme_id: Primary key.

        Returns:
            The detail payload.
        """
        summary = await self.get_summary(programme_id)

        run_result = await self._session.execute(
            select(
                PredictionRun.run_id,
                PredictionRun.generated_at,
                User.full_name.label("generated_by_name"),
                PredictionRun.ranked_count,
                PredictionRun.excluded_count,
                PredictionRun.candidate_pool_size,
                PredictionRun.elapsed_ms,
                PredictionRun.is_superseded,
            )
            .join(User, User.user_id == PredictionRun.generated_by_user_id)
            .where(PredictionRun.programme_id == programme_id)
            .order_by(PredictionRun.generated_at.desc())
            .limit(1)
        )
        run_row = run_result.one_or_none()
        latest_run = ProgrammeRunSummary.model_validate(run_row) if run_row else None

        allocations = await self._session.execute(
            select(func.count())
            .select_from(Allocation)
            .where(Allocation.programme_id == programme_id)
        )

        return ProgrammeDetail(
            programme=summary,
            has_run=latest_run is not None,
            latest_run=latest_run,
            allocation_count=int(allocations.scalar_one()),
            timeline=await self._timeline(programme_id, summary),
        )

    async def _timeline(
        self, programme_id: int, summary: ProgrammeSummary
    ) -> list[ProgrammeStatusEvent]:
        """Build the lifecycle timeline from the audit trail.

        Derived from `audit_logs` rather than from a separate history table: the audit
        entries already exist, are append-only, and are the record an investigator
        would consult — a second history table could disagree with them.

        Args:
            programme_id: Primary key.
            summary: The programme, for its creation time.

        Returns:
            Events in chronological order.
        """
        from app.models.system import AuditLog

        result = await self._session.execute(
            select(AuditLog.action, AuditLog.created_at, AuditLog.detail, User.full_name)
            .outerjoin(User, User.user_id == AuditLog.actor_user_id)
            .where(
                AuditLog.entity_type.in_(("TRAINING_PROGRAMME", "PREDICTION_RUN")),
                AuditLog.entity_id == programme_id,
            )
            .order_by(AuditLog.created_at)
        )
        events = [
            ProgrammeStatusEvent(
                status=row.action,
                occurred_at=row.created_at,
                actor_name=row.full_name,
                detail=row.detail or "",
            )
            for row in result.all()
        ]
        if not events:
            events.append(
                ProgrammeStatusEvent(
                    status="PROGRAMME_CREATED",
                    occurred_at=summary.created_at,
                    actor_name=summary.created_by_name,
                    detail=f'Created "{summary.title}"',
                )
            )
        return events

    async def create(self, payload: ProgrammeCreate, actor_user_id: int) -> ProgrammeSummary:
        """Raise a training request (FR-04).

        The programme starts at `DRAFT` with **no requirements**. FR-05 defines those
        separately, which is what makes the `DRAFT` → `REQUIREMENTS_SET` transition a
        real event rather than a flag.

        Args:
            payload: The request particulars.
            actor_user_id: The raising officer.

        Returns:
            The created programme.

        Raises:
            NotFoundError: If the category or station does not exist.
        """
        if await self._session.get(TrainingCategory, payload.category_id) is None:
            raise NotFoundError("That training category could not be found.")
        if await self._session.get(Station, payload.station_id) is None:
            raise NotFoundError("That venue could not be found.")

        registry = await self._next_registry_number("REQ")
        programme = TrainingProgramme(
            registry_number=registry,
            title=payload.title,
            category_id=payload.category_id,
            required_specialization_area_id=None,
            minimum_experience=0,
            minimum_qualification_level_id=None,
            start_date=payload.start_date,
            end_date=payload.end_date,
            station_id=payload.station_id,
            expected_participants=payload.expected_participants,
            status=ProgrammeStatus.DRAFT,
            created_by_user_id=actor_user_id,
        )
        self._session.add(programme)
        await self._session.flush()

        await self._audit.record(
            AuditAction.PROGRAMME_CREATED,
            entity_type="TRAINING_PROGRAMME",
            entity_id=programme.programme_id,
            after={"title": payload.title, "registry_number": registry},
            detail=f'Created "{payload.title}" ({registry}).',
        )
        return await self.get_summary(programme.programme_id)

    async def update(self, programme_id: int, payload: ProgrammeUpdate) -> ProgrammeSummary:
        """Edit a programme's particulars.

        Blocked once the programme is `ALLOCATED` or beyond: a trainer has accepted a
        commitment by then, and silently moving the dates would change what they
        agreed to.

        Args:
            programme_id: Primary key.
            payload: The fields to change.

        Returns:
            The updated programme.

        Raises:
            ConflictError: If the programme is too far along to edit.
        """
        programme = await self.load(programme_id)
        if programme.status not in EDITABLE_STATUSES:
            raise ConflictError(
                f"This programme is at {programme.status} and can no longer be edited. "
                "A trainer has already been assigned to it; cancel it and raise a new "
                "request if the particulars must change."
            )

        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field in (
            "title",
            "category_id",
            "start_date",
            "end_date",
            "station_id",
            "expected_participants",
        ):
            value = getattr(payload, field)
            if value is not None and value != getattr(programme, field):
                before[field] = str(getattr(programme, field))
                after[field] = str(value)
                setattr(programme, field, value)

        start = payload.start_date or programme.start_date
        end = payload.end_date or programme.end_date
        if end < start:
            raise ConflictError("The course cannot end before it starts.")

        await self._session.flush()
        if after:
            await self._audit.record(
                AuditAction.USER_MODIFIED,
                entity_type="TRAINING_PROGRAMME",
                entity_id=programme_id,
                before=before,
                after=after,
                detail=f'Edited "{programme.title}".',
            )
        return await self.get_summary(programme_id)

    async def set_requirements(
        self, programme_id: int, payload: RequirementsInput
    ) -> ProgrammeSummary:
        """Define what a programme needs (FR-05).

        If a prediction run already exists, sets
        ``requirements_changed_since_prediction`` and audits `REQUIREMENTS_CHANGED`.
        That flag is what raises the frontend's amber re-run banner: the ranking on
        screen was computed against different criteria and is now stale, and an
        officer approving from it would be approving against requirements that no
        longer apply.

        Args:
            programme_id: Primary key.
            payload: The requirements.

        Returns:
            The updated programme.

        Raises:
            NotFoundError: If a referenced row does not exist.
            ConflictError: If the programme is past the point of redefinition.
        """
        programme = await self.load(programme_id)
        if programme.status in (
            ProgrammeStatus.CONDUCTED,
            ProgrammeStatus.EVALUATED,
            ProgrammeStatus.CANCELLED,
        ):
            raise ConflictError(
                f"This programme is at {programme.status}; its requirements can no "
                "longer be changed."
            )

        area = await self._session.get(SpecializationArea, payload.required_specialization_area_id)
        if area is None:
            raise NotFoundError("That specialisation area could not be found.")
        if payload.minimum_qualification_level_id is not None:
            level = await self._session.get(
                QualificationLevel, payload.minimum_qualification_level_id
            )
            if level is None:
                raise NotFoundError("That qualification level could not be found.")

        before = {
            "required_specialization_area_id": programme.required_specialization_area_id,
            "minimum_experience": programme.minimum_experience,
            "minimum_qualification_level_id": programme.minimum_qualification_level_id,
        }
        after = {
            "required_specialization_area_id": payload.required_specialization_area_id,
            "minimum_experience": payload.minimum_experience,
            "minimum_qualification_level_id": payload.minimum_qualification_level_id,
        }
        changed = before != after

        programme.required_specialization_area_id = payload.required_specialization_area_id
        programme.minimum_experience = payload.minimum_experience
        programme.minimum_qualification_level_id = payload.minimum_qualification_level_id
        programme.requirements_set_at = self._clock.now()

        existing_run = await self._session.execute(
            select(PredictionRun.run_id).where(PredictionRun.programme_id == programme_id).limit(1)
        )
        has_run = existing_run.scalar_one_or_none() is not None

        if programme.status == ProgrammeStatus.DRAFT:
            programme.status = ProgrammeStatus.REQUIREMENTS_SET

        if has_run and changed:
            programme.requirements_changed_since_prediction = True

        await self._session.flush()
        await self._audit.record(
            AuditAction.REQUIREMENTS_CHANGED if has_run else AuditAction.REQUIREMENTS_DEFINED,
            entity_type="TRAINING_PROGRAMME",
            entity_id=programme_id,
            before=before if has_run else None,
            after=after,
            detail=(
                f'Requirements changed for "{programme.title}"; the existing ranking '
                "is now out of date."
                if has_run and changed
                else f'Requirements defined for "{programme.title}": {area.name}.'
            ),
        )
        return await self.get_summary(programme_id)

    async def delete(self, programme_id: int) -> None:
        """Delete a programme, only from `DRAFT` or `REQUIREMENTS_SET`.

        Anything further along has allocation history, which is part of a decision
        record and must survive. Those are cancelled instead.

        Args:
            programme_id: Primary key.

        Raises:
            ConflictError: If the programme has progressed too far.
        """
        programme = await self.load(programme_id)
        if programme.status not in DELETABLE_STATUSES:
            raise ConflictError(
                f"This programme is at {programme.status} and cannot be deleted — it "
                "has allocation history that forms part of the decision record. "
                "Cancel it instead, which preserves the record."
            )
        title = programme.title
        registry = programme.registry_number
        await self._session.delete(programme)
        await self._session.flush()
        await self._audit.record(
            AuditAction.USER_MODIFIED,
            entity_type="TRAINING_PROGRAMME",
            entity_id=programme_id,
            before={"title": title, "registry_number": registry},
            detail=f'Deleted draft programme "{title}" ({registry}).',
        )

    async def cancel(self, programme_id: int, reason: str) -> ProgrammeSummary:
        """Cancel a programme, preserving its record.

        Args:
            programme_id: Primary key.
            reason: Why.

        Returns:
            The cancelled programme.

        Raises:
            ConflictError: If it is already finished or cancelled.
        """
        programme = await self.load(programme_id)
        if programme.status in (ProgrammeStatus.EVALUATED, ProgrammeStatus.CANCELLED):
            raise ConflictError(f"This programme is already {programme.status.lower()}.")
        previous = programme.status
        programme.status = ProgrammeStatus.CANCELLED
        await self._session.flush()
        await self._audit.record(
            AuditAction.USER_MODIFIED,
            entity_type="TRAINING_PROGRAMME",
            entity_id=programme_id,
            before={"status": previous},
            after={"status": ProgrammeStatus.CANCELLED.value},
            detail=f"Cancelled: {reason}",
        )
        return await self.get_summary(programme_id)

    async def _next_registry_number(self, family: str) -> str:
        """Draw a registry number from the database's own sequence (§5.9).

        Uses ``next_registry_number()`` rather than formatting in Python, so the number
        comes from the same concurrency-safe source under simultaneous requests.
        ``MAX(id) + 1`` would issue duplicates under concurrent approvals, and a
        duplicate registry number on a government record is a serious defect.

        Args:
            family: ``REQ``, ``ALL``, or ``EVL``.

        Returns:
            e.g. ``TPS/REQ/2026/0132``.
        """
        from sqlalchemy import text

        result = await self._session.execute(
            text("SELECT next_registry_number(:family)"), {"family": family}
        )
        return str(result.scalar_one())
