"""Trainer profile and credential management (FR-02, FR-03).

Imports no `fastapi` (B7). Object-level ownership is enforced here rather than in the
router, because "a trainer may edit **their own** qualifications" is a business rule,
not an HTTP concern — and putting it in the router means every new route has to
remember it (§7.1).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.enums import AuditAction, AvailabilityStatus
from app.models.identity import User
from app.models.programme import TrainingProgramme
from app.models.reference import (
    Institution,
    ProficiencyLevel,
    QualificationLevel,
    SpecializationArea,
    Station,
)
from app.models.trainer import (
    Trainer,
    TrainerQualification,
    TrainerSpecialization,
    TrainerUnavailability,
)
from app.schemas.trainer import (
    EvaluationSummary,
    QualificationCreate,
    QualificationRead,
    SpecializationCreate,
    SpecializationRead,
    TrainerDetail,
    TrainerSelfUpdate,
    UnavailabilityCreate,
    UnavailabilityRead,
)
from app.services.audit_service import AuditService

#: Allocation statuses that occupy a trainer right now.
ACTIVE_ALLOCATION_STATUSES = ("PENDING_TRAINER", "CONFIRMED", "CONDUCTED")


class TrainerService:
    """Reads and writes over a trainer's own profile.

    Args:
        session: The request's session.
        audit: Audit service sharing the same transaction (B8).
        clock: Injected clock. A service that reads the wall clock cannot be tested
            deterministically, and two of the rules here — "is this course still in
            the future?" and "is this year in the future?" — depend on it.
    """

    def __init__(self, session: AsyncSession, audit: AuditService, clock: Clock) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock

    async def _load(self, trainer_id: int) -> Trainer:
        """Load a trainer or raise.

        Args:
            trainer_id: Primary key.

        Returns:
            The trainer entity.

        Raises:
            NotFoundError: If no such trainer exists.
        """
        trainer = await self._session.get(Trainer, trainer_id)
        if trainer is None:
            raise NotFoundError("That trainer record could not be found.")
        return trainer

    async def get_detail(self, trainer_id: int) -> TrainerDetail:
        """Build a trainer's full profile.

        Four small queries rather than one wide join: qualifications, specialisations,
        absences, and evaluations are independent one-to-many collections, and joining
        them in a single statement multiplies the rows by each other's cardinality.

        Args:
            trainer_id: Primary key.

        Returns:
            The full profile.

        Raises:
            NotFoundError: If no such trainer exists.
        """
        base = await self._session.execute(
            select(
                Trainer.trainer_id,
                Trainer.user_id,
                User.full_name,
                Trainer.force_number,
                Trainer.years_experience,
                Trainer.availability_status,
                Trainer.contact_number,
                Trainer.profile_completeness,
                Trainer.date_of_enlistment,
                Trainer.bio,
            )
            .join(User, User.user_id == Trainer.user_id)
            .where(Trainer.trainer_id == trainer_id)
        )
        row = base.one_or_none()
        if row is None:
            raise NotFoundError("That trainer record could not be found.")

        from app.repositories.trainer_repo import TrainerRepository

        directory = await TrainerRepository(self._session).get_by_id(trainer_id)
        if directory is None:  # pragma: no cover - impossible given the check above
            raise NotFoundError("That trainer record could not be found.")

        qualifications = await self.list_qualifications(trainer_id)
        specializations = await self.list_specializations(trainer_id)
        unavailability = await self.list_unavailability(trainer_id)
        evaluations = await self.list_evaluations(trainer_id)

        workload = await self._session.execute(
            select(
                func.count().filter(Allocation.status.in_(ACTIVE_ALLOCATION_STATUSES)),
                func.max(Allocation.approval_date),
            ).where(Allocation.trainer_id == trainer_id)
        )
        active_count, last_assigned = workload.one()

        mean: Decimal | None = None
        if evaluations:
            mean = sum((e.score_awarded for e in evaluations), start=Decimal("0")) / Decimal(
                len(evaluations)
            )

        return TrainerDetail(
            trainer_id=directory.trainer_id,
            user_id=directory.user_id,
            full_name=directory.full_name,
            force_number=directory.force_number,
            police_rank=directory.police_rank,
            station=directory.station,
            region=directory.region,
            directorate=directory.directorate,
            years_experience=directory.years_experience,
            availability_status=directory.availability_status,
            contact_number=directory.contact_number,
            profile_completeness=directory.profile_completeness,
            date_of_enlistment=row.date_of_enlistment,
            bio=row.bio,
            qualifications=qualifications,
            specializations=specializations,
            unavailability=unavailability,
            performance_history=evaluations,
            current_allocations=int(active_count or 0),
            last_assigned_date=last_assigned,
            mean_score=mean,
        )

    async def list_qualifications(self, trainer_id: int) -> list[QualificationRead]:
        """Return a trainer's qualifications, highest first."""
        result = await self._session.execute(
            select(
                TrainerQualification.qualification_id,
                TrainerQualification.trainer_id,
                TrainerQualification.qualification_name,
                QualificationLevel.code.label("qualification_level"),
                TrainerQualification.level_id,
                Institution.name.label("institution_name"),
                TrainerQualification.institution_id,
                TrainerQualification.year_obtained,
            )
            .join(QualificationLevel, QualificationLevel.level_id == TrainerQualification.level_id)
            .join(Institution, Institution.institution_id == TrainerQualification.institution_id)
            .where(TrainerQualification.trainer_id == trainer_id)
            .order_by(QualificationLevel.rank_order.desc())
        )
        return [QualificationRead.model_validate(r) for r in result.all()]

    async def list_specializations(self, trainer_id: int) -> list[SpecializationRead]:
        """Return a trainer's specialisations, strongest first."""
        result = await self._session.execute(
            select(
                TrainerSpecialization.specialization_id,
                TrainerSpecialization.trainer_id,
                SpecializationArea.name.label("specialization_area"),
                TrainerSpecialization.specialization_area_id,
                ProficiencyLevel.code.label("proficiency_level"),
                TrainerSpecialization.proficiency_level_id,
                TrainerSpecialization.years_in_area,
            )
            .join(
                SpecializationArea,
                SpecializationArea.specialization_area_id
                == TrainerSpecialization.specialization_area_id,
            )
            .join(
                ProficiencyLevel,
                ProficiencyLevel.level_id == TrainerSpecialization.proficiency_level_id,
            )
            .where(TrainerSpecialization.trainer_id == trainer_id)
            .order_by(ProficiencyLevel.rank_order.desc())
        )
        return [SpecializationRead.model_validate(r) for r in result.all()]

    async def list_unavailability(self, trainer_id: int) -> list[UnavailabilityRead]:
        """Return a trainer's declared absence windows, soonest first."""
        result = await self._session.execute(
            select(
                TrainerUnavailability.unavailability_id,
                TrainerUnavailability.trainer_id,
                TrainerUnavailability.start_date,
                TrainerUnavailability.end_date,
                TrainerUnavailability.reason,
                TrainerUnavailability.category,
            )
            .where(TrainerUnavailability.trainer_id == trainer_id)
            .order_by(TrainerUnavailability.start_date)
        )
        return [UnavailabilityRead.model_validate(r) for r in result.all()]

    async def list_evaluations(self, trainer_id: int) -> list[EvaluationSummary]:
        """Return a trainer's evaluation history, most recent first."""
        evaluator = select(User).subquery()
        result = await self._session.execute(
            select(
                PerformanceEvaluation.evaluation_id,
                PerformanceEvaluation.allocation_id,
                PerformanceEvaluation.trainer_id,
                PerformanceEvaluation.programme_id,
                TrainingProgramme.title.label("programme_title"),
                PerformanceEvaluation.score_awarded,
                PerformanceEvaluation.evaluator_comments,
                PerformanceEvaluation.evaluated_by_user_id.label("evaluated_by"),
                evaluator.c.full_name.label("evaluated_by_name"),
                PerformanceEvaluation.evaluation_date,
            )
            .join(
                TrainingProgramme,
                TrainingProgramme.programme_id == PerformanceEvaluation.programme_id,
            )
            .join(evaluator, evaluator.c.user_id == PerformanceEvaluation.evaluated_by_user_id)
            .where(PerformanceEvaluation.trainer_id == trainer_id)
            .order_by(PerformanceEvaluation.evaluation_date.desc())
        )
        return [EvaluationSummary.model_validate(r) for r in result.all()]

    async def update_profile(self, trainer_id: int, payload: TrainerSelfUpdate) -> TrainerDetail:
        """Update a trainer's own particulars (FR-02).

        Args:
            trainer_id: Whose profile.
            payload: The fields to change.

        Returns:
            The updated profile.

        Raises:
            NotFoundError: If the trainer or a referenced row does not exist.
        """
        trainer = await self._load(trainer_id)
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}

        if payload.rank_id is not None and payload.rank_id != trainer.rank_id:
            before["rank_id"], after["rank_id"] = trainer.rank_id, payload.rank_id
            trainer.rank_id = payload.rank_id
        if payload.station_id is not None and payload.station_id != trainer.station_id:
            if await self._session.get(Station, payload.station_id) is None:
                raise NotFoundError("That station could not be found.")
            before["station_id"], after["station_id"] = trainer.station_id, payload.station_id
            trainer.station_id = payload.station_id
        if payload.years_experience is not None:
            before["years_experience"] = trainer.years_experience
            after["years_experience"] = payload.years_experience
            trainer.years_experience = payload.years_experience
        if payload.contact_number is not None:
            before["contact_number"] = trainer.contact_number
            after["contact_number"] = payload.contact_number
            trainer.contact_number = payload.contact_number
        if payload.bio is not None:
            before["bio"], after["bio"] = trainer.bio, payload.bio
            trainer.bio = payload.bio

        trainer.profile_completeness = await self._recompute_completeness(trainer)
        await self._session.flush()

        if after:
            await self._audit.record(
                AuditAction.PROFILE_UPDATED,
                entity_type="TRAINER",
                entity_id=trainer_id,
                before=before,
                after=after,
                detail="Trainer updated their own profile.",
            )
        return await self.get_detail(trainer_id)

    async def set_availability(self, trainer_id: int, status: str) -> TrainerDetail:
        """Change a trainer's availability (§6.3).

        Refuses ``AVAILABLE`` while a confirmed allocation is in progress: a trainer
        cannot be simultaneously committed to a course and open for another, and
        allowing it would let the scoring engine double-book them.

        Args:
            trainer_id: Whose availability.
            status: The new status.

        Returns:
            The updated profile.

        Raises:
            ConflictError: If setting AVAILABLE while committed.
        """
        trainer = await self._load(trainer_id)
        previous = trainer.availability_status

        if status == AvailabilityStatus.AVAILABLE and previous != AvailabilityStatus.AVAILABLE:
            result = await self._session.execute(
                select(TrainingProgramme.title)
                .join(Allocation, Allocation.programme_id == TrainingProgramme.programme_id)
                .where(
                    Allocation.trainer_id == trainer_id,
                    Allocation.status == "CONFIRMED",
                    TrainingProgramme.end_date >= self._clock.now().date(),
                )
                .limit(1)
            )
            conflicting = result.scalar_one_or_none()
            if conflicting is not None:
                raise ConflictError(
                    f"You cannot mark yourself available while you are confirmed to "
                    f"deliver {conflicting}. Withdraw from that course first, or ask "
                    "your Training Administrator to reassign it."
                )

        trainer.availability_status = status
        await self._session.flush()
        await self._audit.record(
            AuditAction.AVAILABILITY_CHANGED,
            entity_type="TRAINER",
            entity_id=trainer_id,
            before={"availability_status": previous},
            after={"availability_status": status},
            detail=f"Availability changed from {previous} to {status}.",
        )
        return await self.get_detail(trainer_id)

    async def add_qualification(
        self, trainer_id: int, payload: QualificationCreate
    ) -> QualificationRead:
        """Append a qualification (FR-03).

        **Appends — never overwrites.** FR-03 is explicit, and a POST that replaced the
        list would silently delete a trainer's record of a degree they still hold.

        Args:
            trainer_id: Whose qualification.
            payload: The qualification.

        Returns:
            The created row.

        Raises:
            NotFoundError: If the level or institution does not exist.
            ConflictError: If the year is in the future.
        """
        await self._load(trainer_id)
        if await self._session.get(QualificationLevel, payload.level_id) is None:
            raise NotFoundError("That qualification level could not be found.")
        if await self._session.get(Institution, payload.institution_id) is None:
            raise NotFoundError("That institution could not be found.")
        if payload.year_obtained > self._clock.now().year:
            raise ConflictError(
                f"The year obtained ({payload.year_obtained}) is in the future.",
                errors=[{"field": "yearObtained", "message": "Cannot be a future year."}],
            )

        row = TrainerQualification(
            trainer_id=trainer_id,
            qualification_name=payload.qualification_name,
            level_id=payload.level_id,
            institution_id=payload.institution_id,
            year_obtained=payload.year_obtained,
        )
        self._session.add(row)
        await self._session.flush()
        await self._refresh_completeness(trainer_id)
        await self._audit.record(
            AuditAction.PROFILE_UPDATED,
            entity_type="TRAINER_QUALIFICATION",
            entity_id=row.qualification_id,
            after={"qualification_name": payload.qualification_name},
            detail=f"Added qualification '{payload.qualification_name}'.",
        )
        created = [
            q
            for q in await self.list_qualifications(trainer_id)
            if q.qualification_id == row.qualification_id
        ]
        return created[0]

    async def delete_qualification(self, trainer_id: int, qualification_id: int) -> None:
        """Remove a qualification, checking ownership (§7.1 layer 2).

        Args:
            trainer_id: The caller's trainer id.
            qualification_id: The row to remove.

        Raises:
            NotFoundError: If it does not exist.
            ForbiddenError: If it belongs to another trainer.
        """
        row = await self._session.get(TrainerQualification, qualification_id)
        if row is None:
            raise NotFoundError("That qualification could not be found.")
        if row.trainer_id != trainer_id:
            raise ForbiddenError("You may only change your own qualifications.")
        await self._session.delete(row)
        await self._session.flush()
        await self._refresh_completeness(trainer_id)
        await self._audit.record(
            AuditAction.PROFILE_UPDATED,
            entity_type="TRAINER_QUALIFICATION",
            entity_id=qualification_id,
            before={"qualification_name": row.qualification_name},
            detail=f"Removed qualification '{row.qualification_name}'.",
        )

    async def add_specialization(
        self, trainer_id: int, payload: SpecializationCreate
    ) -> SpecializationRead:
        """Add a specialisation (FR-03).

        A duplicate area returns **409, not a silent update**. The database enforces
        one proficiency per area; quietly overwriting would let a trainer downgrade
        their own recorded level by re-adding it, with no trace.

        Args:
            trainer_id: Whose specialisation.
            payload: The specialisation.

        Returns:
            The created row.

        Raises:
            NotFoundError: If the area or level does not exist.
            ConflictError: If the trainer already holds that area.
        """
        await self._load(trainer_id)
        area = await self._session.get(SpecializationArea, payload.specialization_area_id)
        if area is None:
            raise NotFoundError("That specialisation area could not be found.")
        if await self._session.get(ProficiencyLevel, payload.proficiency_level_id) is None:
            raise NotFoundError("That proficiency level could not be found.")

        existing = await self._session.execute(
            select(TrainerSpecialization.specialization_id).where(
                TrainerSpecialization.trainer_id == trainer_id,
                TrainerSpecialization.specialization_area_id == payload.specialization_area_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                f"You already have {area.name} recorded. Edit the existing entry to "
                "change your proficiency level.",
                errors=[{"field": "specializationAreaId", "message": "Already recorded."}],
            )

        row = TrainerSpecialization(
            trainer_id=trainer_id,
            specialization_area_id=payload.specialization_area_id,
            proficiency_level_id=payload.proficiency_level_id,
            years_in_area=payload.years_in_area,
        )
        self._session.add(row)
        await self._session.flush()
        await self._refresh_completeness(trainer_id)
        await self._audit.record(
            AuditAction.PROFILE_UPDATED,
            entity_type="TRAINER_SPECIALIZATION",
            entity_id=row.specialization_id,
            after={"specialization_area": area.name},
            detail=f"Added specialisation '{area.name}'.",
        )
        created = [
            s
            for s in await self.list_specializations(trainer_id)
            if s.specialization_id == row.specialization_id
        ]
        return created[0]

    async def delete_specialization(self, trainer_id: int, specialization_id: int) -> None:
        """Remove a specialisation, checking ownership.

        Args:
            trainer_id: The caller's trainer id.
            specialization_id: The row to remove.

        Raises:
            NotFoundError: If it does not exist.
            ForbiddenError: If it belongs to another trainer.
        """
        row = await self._session.get(TrainerSpecialization, specialization_id)
        if row is None:
            raise NotFoundError("That specialisation could not be found.")
        if row.trainer_id != trainer_id:
            raise ForbiddenError("You may only change your own specialisations.")
        await self._session.delete(row)
        await self._session.flush()
        await self._refresh_completeness(trainer_id)
        await self._audit.record(
            AuditAction.PROFILE_UPDATED,
            entity_type="TRAINER_SPECIALIZATION",
            entity_id=specialization_id,
            detail="Removed a specialisation.",
        )

    async def add_unavailability(
        self, trainer_id: int, payload: UnavailabilityCreate
    ) -> UnavailabilityRead:
        """Declare an absence window.

        Overlaps are refused. The database has an ``EXCLUDE`` constraint preventing
        them, but catching it here produces a sentence an officer can act on instead
        of a constraint-violation error.

        Args:
            trainer_id: Whose absence.
            payload: The window.

        Returns:
            The created row.

        Raises:
            ConflictError: If it overlaps an existing window.
        """
        await self._load(trainer_id)
        clash = await self._session.execute(
            select(TrainerUnavailability.start_date, TrainerUnavailability.end_date).where(
                TrainerUnavailability.trainer_id == trainer_id,
                TrainerUnavailability.start_date <= payload.end_date,
                TrainerUnavailability.end_date >= payload.start_date,
            )
        )
        overlap = clash.first()
        if overlap is not None:
            raise ConflictError(
                f"You already have an absence recorded from {overlap.start_date} to "
                f"{overlap.end_date}, which overlaps these dates."
            )

        row = TrainerUnavailability(
            trainer_id=trainer_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            reason=payload.reason,
            category=payload.category,
        )
        self._session.add(row)
        await self._session.flush()
        await self._audit.record(
            AuditAction.AVAILABILITY_CHANGED,
            entity_type="TRAINER_UNAVAILABILITY",
            entity_id=row.unavailability_id,
            after={
                "start_date": payload.start_date.isoformat(),
                "end_date": payload.end_date.isoformat(),
                "category": payload.category,
            },
            detail=f"Declared absence: {payload.reason}",
        )
        return UnavailabilityRead(
            unavailability_id=row.unavailability_id,
            trainer_id=trainer_id,
            start_date=row.start_date,
            end_date=row.end_date,
            reason=row.reason,
            category=row.category,
        )

    async def delete_unavailability(self, trainer_id: int, unavailability_id: int) -> None:
        """Remove an absence window, checking ownership.

        Args:
            trainer_id: The caller's trainer id.
            unavailability_id: The row to remove.

        Raises:
            NotFoundError: If it does not exist.
            ForbiddenError: If it belongs to another trainer.
        """
        row = await self._session.get(TrainerUnavailability, unavailability_id)
        if row is None:
            raise NotFoundError("That absence record could not be found.")
        if row.trainer_id != trainer_id:
            raise ForbiddenError("You may only change your own absence records.")
        await self._session.delete(row)
        await self._session.flush()
        await self._audit.record(
            AuditAction.AVAILABILITY_CHANGED,
            entity_type="TRAINER_UNAVAILABILITY",
            entity_id=unavailability_id,
            detail="Removed a declared absence.",
        )

    async def _refresh_completeness(self, trainer_id: int) -> None:
        """Recompute and store profile completeness after a credential change."""
        trainer = await self._load(trainer_id)
        trainer.profile_completeness = await self._recompute_completeness(trainer)
        await self._session.flush()

    async def _recompute_completeness(self, trainer: Trainer) -> int:
        """Derive profile completeness from field presence.

        Contributes 35% of the confidence level, so it is stored rather than computed
        on read — a prediction's confidence must be reproducible exactly as it stood
        (conflict C6 in Phase 1).

        Five equally weighted components: contact number, enlistment date, biography,
        at least one qualification, at least one specialisation.

        Args:
            trainer: The trainer.

        Returns:
            A score from 0 to 100.
        """
        qualifications = await self._session.execute(
            select(func.count())
            .select_from(TrainerQualification)
            .where(TrainerQualification.trainer_id == trainer.trainer_id)
        )
        specialisations = await self._session.execute(
            select(func.count())
            .select_from(TrainerSpecialization)
            .where(TrainerSpecialization.trainer_id == trainer.trainer_id)
        )
        components = (
            bool(trainer.contact_number and trainer.contact_number.strip()),
            trainer.date_of_enlistment is not None,
            bool(trainer.bio and trainer.bio.strip()),
            int(qualifications.scalar_one()) > 0,
            int(specialisations.scalar_one()) > 0,
        )
        return round(sum(components) / len(components) * 100)
