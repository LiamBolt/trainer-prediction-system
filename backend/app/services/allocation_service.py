"""The allocation lifecycle (FR-08, FR-09). Imports no `fastapi` (B7).

This module writes the only records in the system that are decisions rather than
observations, and everything in it follows from that.

**Approval is one transaction or none of it.** Create the allocation, freeze the
snapshot, advance the programme, notify the trainer, write the audit entry — all or
nothing. A partial success here is a notified trainer with no allocation, or an
allocation nobody was told about, and either one is discovered weeks later by a person,
not by a monitor.

**The gates are re-checked at approval.** A ranking is a photograph. Between the run
and the approval a trainer may have declared leave, accepted another course, or been
marked unavailable. Approving from a stale ranking would post an officer to a course
they cannot attend, so the same gate code that produced the ranking runs again against
live data, and refuses.

**The snapshot is frozen, not re-derived.** ``frozen_score`` and its four companions
are copied from the prediction and never recomputed. An evaluation recorded next month
changes tomorrow's rankings — it must not change the justification for a decision taken
today. That difference is what separates an audit record from a rendering.
"""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import BusinessRuleViolation, ConflictError, ForbiddenError, NotFoundError
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.enums import (
    AllocationStatus,
    AuditAction,
    AvailabilityStatus,
    NotificationType,
    ProgrammeStatus,
)
from app.models.identity import User
from app.models.prediction import Prediction, PredictionRun
from app.models.programme import TrainingProgramme
from app.models.reference import PoliceRank, Station
from app.models.trainer import Trainer
from app.repositories.trainer_repo import TrainerRepository
from app.schemas.allocation import AllocationListItem
from app.schemas.prediction import CriterionScoreRead
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.prediction.gates import evaluate_gates
from app.services.prediction.types import CandidateFacts, ProgrammeRequirements

logger = structlog.get_logger(__name__)

#: Statuses in which an allocation still holds the programme. A programme with one of
#: these cannot receive a second allocation — a course has one trainer, and a second
#: approval would be a silent double-posting rather than a correction.
LIVE_STATUSES = (
    AllocationStatus.PENDING_TRAINER.value,
    AllocationStatus.CONFIRMED.value,
    AllocationStatus.CONDUCTED.value,
    AllocationStatus.EVALUATED.value,
)


class AllocationService:
    """Approves, promotes, and closes allocations.

    Args:
        session: The request's session. One transaction spans the whole operation.
        audit: Audit service sharing that transaction (B8).
        notifications: Notification service, also in-transaction.
        clock: Injected clock.
    """

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        notifications: NotificationService,
        clock: Clock,
    ) -> None:
        self._session = session
        self._audit = audit
        self._notifications = notifications
        self._clock = clock
        #: Ids queued for background dispatch once the transaction commits.
        self.pending_dispatch: list[int] = []

    # ------------------------------------------------------------------ reads

    def list_query(self) -> Select[Any]:
        """Build the base projection for the allocation list.

        Returns:
            A ``SELECT`` ready for filtering, sorting, and pagination.
        """
        approver = User.__table__.alias("approver")
        trainer_user = User.__table__.alias("trainer_user")
        approver_rank = PoliceRank.__table__.alias("approver_rank")
        trainer_rank = PoliceRank.__table__.alias("trainer_rank")

        return (
            select(
                Allocation.allocation_id,
                Allocation.prediction_id,
                Allocation.programme_id,
                Allocation.trainer_id,
                Allocation.registry_number,
                Allocation.approved_by_user_id.label("approved_by"),
                approver.c.full_name.label("approved_by_name"),
                func.coalesce(approver_rank.c.code, "").label("approved_by_rank"),
                Allocation.status,
                Allocation.approval_date,
                func.coalesce(Allocation.remarks, "").label("remarks"),
                Allocation.frozen_score,
                Allocation.frozen_breakdown,
                Allocation.frozen_rank_position,
                Allocation.frozen_weights,
                Allocation.frozen_rationale,
                Allocation.weights_were_simulated,
                Allocation.decline_reason,
                Allocation.declined_at,
                Allocation.responded_at,
                Allocation.superseded_by_allocation_id,
                TrainingProgramme.title.label("programme_title"),
                TrainingProgramme.registry_number.label("programme_registry_number"),
                TrainingProgramme.start_date.label("programme_start_date"),
                TrainingProgramme.end_date.label("programme_end_date"),
                Station.name.label("programme_location"),
                trainer_user.c.full_name.label("trainer_name"),
                trainer_rank.c.code.label("trainer_rank"),
                Trainer.force_number.label("trainer_force_number"),
                Station.name.label("trainer_station"),
                PerformanceEvaluation.evaluation_id,
            )
            .join(
                TrainingProgramme,
                TrainingProgramme.programme_id == Allocation.programme_id,
            )
            .join(Station, Station.station_id == TrainingProgramme.station_id)
            .join(Trainer, Trainer.trainer_id == Allocation.trainer_id)
            .join(trainer_user, trainer_user.c.user_id == Trainer.user_id)
            .join(trainer_rank, trainer_rank.c.rank_id == Trainer.rank_id)
            .join(approver, approver.c.user_id == Allocation.approved_by_user_id)
            .outerjoin(approver_rank, approver_rank.c.rank_id == approver.c.rank_id)
            .outerjoin(
                PerformanceEvaluation,
                PerformanceEvaluation.allocation_id == Allocation.allocation_id,
            )
        )

    @staticmethod
    def apply_filters(
        query: Select[Any],
        *,
        status: str | None = None,
        programme_id: int | None = None,
        trainer_id: int | None = None,
        approved_by: int | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> Select[Any]:
        """Apply list filters (§6.7).

        Args:
            query: The base query.
            status: Allocation status.
            programme_id: One programme.
            trainer_id: One trainer.
            approved_by: The approving Administrator.
            date_from: Approved on or after.
            date_to: Approved on or before.

        Returns:
            The filtered query.
        """
        if status:
            query = query.where(Allocation.status == status)
        if programme_id is not None:
            query = query.where(Allocation.programme_id == programme_id)
        if trainer_id is not None:
            query = query.where(Allocation.trainer_id == trainer_id)
        if approved_by is not None:
            query = query.where(Allocation.approved_by_user_id == approved_by)
        if date_from is not None:
            query = query.where(Allocation.approval_date >= date_from)
        if date_to is not None:
            query = query.where(
                Allocation.approval_date < date_to + datetime.timedelta(days=1)
            )
        return query

    async def count(self, query: Select[Any]) -> int:
        """Count rows a filtered query would return."""
        result = await self._session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one())

    async def get(self, allocation_id: int) -> AllocationListItem:
        """Return one allocation's full Decision Receipt.

        Args:
            allocation_id: Primary key.

        Returns:
            The receipt payload.

        Raises:
            NotFoundError: If it does not exist.
        """
        result = await self._session.execute(
            self.list_query().where(Allocation.allocation_id == allocation_id)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("That allocation could not be found.")
        return AllocationListItem.model_validate(row)

    async def assignments_for(self, trainer_id: int) -> dict[str, list[AllocationListItem]]:
        """Return a trainer's assignments, split as the screen presents them (§6.3).

        Args:
            trainer_id: The trainer.

        Returns:
            Keys ``pending``, ``upcoming``, and ``past``.
        """
        result = await self._session.execute(
            self.list_query()
            .where(Allocation.trainer_id == trainer_id)
            .order_by(Allocation.approval_date.desc())
        )
        rows = [AllocationListItem.model_validate(row) for row in result.all()]
        return {
            "pending": [r for r in rows if r.status == AllocationStatus.PENDING_TRAINER],
            "upcoming": [r for r in rows if r.status == AllocationStatus.CONFIRMED],
            "past": [
                r
                for r in rows
                if r.status
                in (
                    AllocationStatus.CONDUCTED,
                    AllocationStatus.EVALUATED,
                    AllocationStatus.DECLINED,
                    AllocationStatus.WITHDRAWN,
                )
            ],
        }

    # ------------------------------------------------------------- FR-08

    async def approve(
        self,
        *,
        prediction_id: int,
        actor_user_id: int,
        remarks: str = "",
        expected_programme_id: int | None = None,
        expected_trainer_id: int | None = None,
    ) -> AllocationListItem:
        """Approve an allocation (FR-08, BR-02, BR-06, BR-07).

        BR-06 is why this method exists at all: no allocation is final until an
        Administrator explicitly approves it, so there is no auto-approve path, no
        "accept the top result" shortcut, and no bulk approval anywhere in this service.
        BR-02 — only a Training Administrator may do it — is enforced by the route's
        role gate; this method assumes it and records who acted.

        Everything below happens in the caller's single transaction.

        Args:
            prediction_id: The ranked candidate being approved.
            actor_user_id: The approving Administrator.
            remarks: Optional note for the record.
            expected_programme_id: Optional consistency check from the client.
            expected_trainer_id: Optional consistency check from the client.

        Returns:
            The created allocation, with its frozen snapshot.

        Raises:
            NotFoundError: If the prediction does not exist.
            ConflictError: If the ranking is superseded, the requirements have changed,
                the programme already has a live allocation, or the candidate no longer
                passes the gates.
        """
        prediction = await self._session.get(Prediction, prediction_id)
        if prediction is None:
            raise NotFoundError("That candidate could not be found in any ranking.")

        # Serialise concurrent approvals of the same programme. Two Administrators
        # approving different candidates within the same second would otherwise both
        # pass the "no live allocation" check and both insert.
        locked = await self._session.execute(
            select(TrainingProgramme)
            .where(TrainingProgramme.programme_id == prediction.programme_id)
            .with_for_update()
        )
        programme = locked.scalar_one_or_none()
        if programme is None:
            raise NotFoundError("That training programme could not be found.")

        self._check_client_expectations(prediction, expected_programme_id, expected_trainer_id)

        run = await self._session.get(PredictionRun, prediction.run_id)
        if run is None:  # pragma: no cover — FK makes this unreachable
            raise NotFoundError("The ranking behind this candidate could not be found.")
        if run.is_superseded:
            raise ConflictError(
                "This candidate comes from a ranking that has since been regenerated. "
                "Open the current ranking and approve from there — approving from a "
                "superseded run would record a decision against figures no longer on "
                "screen."
            )
        if programme.requirements_changed_since_prediction:
            raise ConflictError(
                "The requirements for this programme changed after the ranking was "
                "generated, so the ranking no longer reflects what the course needs. "
                "Re-run the prediction before approving."
            )

        await self._assert_no_live_allocation(programme)

        facts = await self._live_facts(programme, prediction.trainer_id)
        await self._recheck_gates(facts, programme, prediction.trainer_id)

        allocation = await self._create_allocation(
            prediction=prediction,
            run=run,
            programme=programme,
            actor_user_id=actor_user_id,
            remarks=remarks,
        )

        await self._audit.record(
            AuditAction.ALLOCATION_APPROVED,
            entity_type="ALLOCATION",
            entity_id=allocation.allocation_id,
            after={
                "registry_number": allocation.registry_number,
                "trainer_id": allocation.trainer_id,
                "programme_id": allocation.programme_id,
                "frozen_score": str(allocation.frozen_score),
                "frozen_rank_position": allocation.frozen_rank_position,
                "prediction_id": prediction.prediction_id,
                "run_id": run.run_id,
            },
            detail=(
                f"Approved {facts.rank_code} {facts.full_name} for "
                f'"{programme.title}" at rank {allocation.frozen_rank_position}, '
                f"score {allocation.frozen_score} ({allocation.registry_number})."
            ),
        )
        return await self.get(allocation.allocation_id)

    async def promote_next(self, allocation_id: int, actor_user_id: int) -> dict[str, Any]:
        """Promote the next-ranked candidate after a decline (FR-08).

        **The existing run is reused.** FR-08 requires that a decline does not trigger a
        new prediction: the ranking already on record is what the Administrator
        approved from, and re-running it would produce a different order against
        different live data, making the sequence of offers impossible to explain from
        one document.

        Candidates between the declined rank and the one offered are passed over only
        for a stated reason — already allocated, or no longer through the gates — and
        each is audited as ``CANDIDATE_SKIPPED``.

        Args:
            allocation_id: The declined allocation.
            actor_user_id: The Administrator promoting.

        Returns:
            The new allocation, the run reused, and the list of skipped candidates.

        Raises:
            ConflictError: If the allocation was not declined, or the ranking is
                exhausted.
        """
        declined = await self._session.get(Allocation, allocation_id)
        if declined is None:
            raise NotFoundError("That allocation could not be found.")
        if declined.status != AllocationStatus.DECLINED:
            raise ConflictError(
                f"This allocation is at {declined.status}. Only a declined allocation "
                "can be replaced by promoting the next candidate."
            )
        if declined.superseded_by_allocation_id is not None:
            raise ConflictError(
                "The next candidate has already been promoted for this decline. "
                "Open the current allocation to see who holds the offer."
            )

        locked = await self._session.execute(
            select(TrainingProgramme)
            .where(TrainingProgramme.programme_id == declined.programme_id)
            .with_for_update()
        )
        programme = locked.scalar_one()
        await self._assert_no_live_allocation(programme)

        prediction = await self._session.get(Prediction, declined.prediction_id)
        if prediction is None:  # pragma: no cover — FK makes this unreachable
            raise NotFoundError("The ranking behind this allocation could not be found.")
        run = await self._session.get(PredictionRun, prediction.run_id)
        if run is None:  # pragma: no cover
            raise NotFoundError("The ranking behind this allocation could not be found.")

        candidates = await self._candidates_after(run.run_id, declined.frozen_rank_position)
        skipped: list[str] = []

        for candidate in candidates:
            facts = await self._live_facts(programme, candidate.trainer_id)
            exclusion = evaluate_gates(facts, await self._requirements(programme))
            if exclusion is not None:
                note = (
                    f"{facts.rank_code} {facts.full_name} (rank "
                    f"{candidate.rank_position}): {exclusion.reason_detail}"
                )
                skipped.append(note)
                await self._audit.record(
                    AuditAction.CANDIDATE_SKIPPED,
                    entity_type="PREDICTION",
                    entity_id=candidate.prediction_id,
                    after={
                        "trainer_id": candidate.trainer_id,
                        "rank_position": candidate.rank_position,
                        "reason": exclusion.reason.value,
                        "business_rule": exclusion.business_rule.value,
                    },
                    detail=f"Passed over — {note}",
                )
                continue

            allocation = await self._create_allocation(
                prediction=candidate,
                run=run,
                programme=programme,
                actor_user_id=actor_user_id,
                remarks=(
                    f"Promoted after {declined.registry_number} was declined at rank "
                    f"{declined.frozen_rank_position}."
                ),
            )
            declined.superseded_by_allocation_id = allocation.allocation_id
            await self._session.flush()

            await self._audit.record(
                AuditAction.ALLOCATION_APPROVED,
                entity_type="ALLOCATION",
                entity_id=allocation.allocation_id,
                after={
                    "registry_number": allocation.registry_number,
                    "trainer_id": allocation.trainer_id,
                    "promoted_from": declined.allocation_id,
                    "run_id": run.run_id,
                    "reused_existing_run": True,
                },
                detail=(
                    f"Promoted {facts.rank_code} {facts.full_name} to rank "
                    f"{allocation.frozen_rank_position} from the same ranking "
                    f"(run {run.run_id}); no new prediction was generated."
                ),
            )
            return {
                "allocation": await self.get(allocation.allocation_id),
                "run_id": run.run_id,
                "skipped": skipped,
                "message": (
                    f"{facts.rank_code} {facts.full_name} has been offered the "
                    f"assignment, taken from the same ranking (run {run.run_id}). "
                    "No new prediction was generated."
                ),
            }

        raise ConflictError(
            "There is no further candidate in this ranking who still meets the "
            f"requirements — {len(candidates)} were considered and "
            f"{len(skipped)} passed over. Re-run the prediction to build a fresh "
            "ranking against current availability."
        )

    async def mark_conducted(self, allocation_id: int) -> AllocationListItem:
        """Record that the training took place (§6.7).

        **This is the gate that unlocks FR-10.** An evaluation cannot be recorded
        against a course nobody has confirmed happened.

        Args:
            allocation_id: Primary key.

        Returns:
            The updated allocation.

        Raises:
            ConflictError: Unless the allocation is CONFIRMED.
        """
        allocation = await self._load(allocation_id)
        if allocation.status != AllocationStatus.CONFIRMED:
            raise ConflictError(
                f"This allocation is at {allocation.status}. Only an assignment the "
                "trainer has confirmed can be marked as conducted."
            )
        allocation.status = AllocationStatus.CONDUCTED.value
        programme = await self._session.get(TrainingProgramme, allocation.programme_id)
        if programme is not None:
            programme.status = ProgrammeStatus.CONDUCTED.value
        await self._session.flush()

        await self._audit.record(
            AuditAction.USER_MODIFIED,
            entity_type="ALLOCATION",
            entity_id=allocation_id,
            before={"status": AllocationStatus.CONFIRMED.value},
            after={"status": AllocationStatus.CONDUCTED.value},
            detail=f"{allocation.registry_number} marked conducted; evaluation may now be recorded.",
        )
        return await self.get(allocation_id)

    async def withdraw(self, allocation_id: int, reason: str) -> AllocationListItem:
        """Withdraw an offer before the trainer answers (§6.7).

        Returns the programme to `PREDICTED`: the ranking still stands, and another
        candidate can be approved from it without a re-run.

        Args:
            allocation_id: Primary key.
            reason: Why — required, and recorded.

        Returns:
            The withdrawn allocation.

        Raises:
            ConflictError: If the trainer has already responded.
        """
        allocation = await self._load(allocation_id)
        if allocation.status != AllocationStatus.PENDING_TRAINER:
            raise ConflictError(
                f"This allocation is at {allocation.status} and can no longer be "
                "withdrawn. The trainer has already responded."
            )
        allocation.status = AllocationStatus.WITHDRAWN.value
        allocation.remarks = (
            f"{allocation.remarks}\nWithdrawn: {reason}" if allocation.remarks else f"Withdrawn: {reason}"
        )
        programme = await self._session.get(TrainingProgramme, allocation.programme_id)
        if programme is not None and programme.status == ProgrammeStatus.AWAITING_RESPONSE:
            programme.status = ProgrammeStatus.PREDICTED.value
        await self._session.flush()

        await self._notify(
            recipient_user_id=await self._trainer_user_id(allocation.trainer_id),
            message=(
                f"The assignment {allocation.registry_number} has been withdrawn by the "
                f"Training Administrator. Reason: {reason}"
            ),
            notification_type=NotificationType.ASSIGNMENT,
            link_to=f"/assignments/{allocation_id}",
        )
        await self._audit.record(
            AuditAction.ALLOCATION_DECLINED,
            entity_type="ALLOCATION",
            entity_id=allocation_id,
            before={"status": AllocationStatus.PENDING_TRAINER.value},
            after={"status": AllocationStatus.WITHDRAWN.value},
            detail=f"{allocation.registry_number} withdrawn: {reason}",
        )
        return await self.get(allocation_id)

    # ------------------------------------------------------------- FR-09

    async def accept(self, allocation_id: int, trainer_id: int) -> AllocationListItem:
        """A trainer accepts an assignment (FR-09).

        Args:
            allocation_id: The assignment.
            trainer_id: The caller's trainer id, from the token — never from the body.

        Returns:
            The confirmed allocation.

        Raises:
            ForbiddenError: If the assignment belongs to another trainer.
            ConflictError: If it is not awaiting a response.
        """
        allocation = await self._load_own(allocation_id, trainer_id)
        if allocation.status != AllocationStatus.PENDING_TRAINER:
            raise ConflictError(
                f"This assignment is at {allocation.status} and is no longer awaiting "
                "your response."
            )
        now = self._clock.now()
        allocation.status = AllocationStatus.CONFIRMED.value
        allocation.responded_at = now

        programme = await self._session.get(TrainingProgramme, allocation.programme_id)
        if programme is not None:
            programme.status = ProgrammeStatus.ALLOCATED.value

        # A confirmed commitment makes the trainer ASSIGNED, which caps the AVAILABILITY
        # criterion at 50 on future runs. The scoring consequence is the point: the
        # system should stop favouring someone who is already committed.
        trainer = await self._session.get(Trainer, trainer_id)
        if trainer is not None and trainer.availability_status == AvailabilityStatus.AVAILABLE:
            trainer.availability_status = AvailabilityStatus.ASSIGNED.value
        await self._session.flush()

        name = await self._trainer_display(trainer_id)
        await self._notify(
            recipient_user_id=allocation.approved_by_user_id,
            message=(
                f"{name} has accepted the assignment for "
                f'"{programme.title if programme else "the programme"}" '
                f"({allocation.registry_number})."
            ),
            notification_type=NotificationType.APPROVAL,
            link_to=f"/allocations/{allocation_id}",
        )
        await self._audit.record(
            AuditAction.ASSIGNMENT_ACCEPTED,
            entity_type="ALLOCATION",
            entity_id=allocation_id,
            before={"status": AllocationStatus.PENDING_TRAINER.value},
            after={"status": AllocationStatus.CONFIRMED.value, "responded_at": now.isoformat()},
            detail=f"{name} accepted {allocation.registry_number}.",
        )
        return await self.get(allocation_id)

    async def decline(
        self, allocation_id: int, trainer_id: int, reason: str
    ) -> AllocationListItem:
        """A trainer declines an assignment (FR-09, BR-07).

        The reason is required at three levels: the schema, this method, and a database
        ``CHECK`` that refuses any ``DECLINED`` row without one. A decline with no
        stated reason gives the Administrator nothing to act on, and BR-07 requires the
        decision — approved *or declined* — to reach the audit log either way.

        The programme returns to `PREDICTED` so the next candidate can be promoted from
        the same ranking without a re-run.

        Args:
            allocation_id: The assignment.
            trainer_id: The caller's trainer id, from the token.
            reason: Why the assignment cannot be taken.

        Returns:
            The declined allocation.

        Raises:
            ForbiddenError: If the assignment belongs to another trainer.
            ConflictError: If it is not awaiting a response.
        """
        allocation = await self._load_own(allocation_id, trainer_id)
        if allocation.status != AllocationStatus.PENDING_TRAINER:
            raise ConflictError(
                f"This assignment is at {allocation.status} and is no longer awaiting "
                "your response."
            )
        now = self._clock.now()
        allocation.status = AllocationStatus.DECLINED.value
        allocation.decline_reason = reason
        allocation.declined_at = now
        allocation.responded_at = now

        programme = await self._session.get(TrainingProgramme, allocation.programme_id)
        if programme is not None and programme.status == ProgrammeStatus.AWAITING_RESPONSE:
            programme.status = ProgrammeStatus.PREDICTED.value
        await self._session.flush()

        name = await self._trainer_display(trainer_id)
        next_up = await self._peek_next(allocation)
        follow_on = (
            f" The next-ranked candidate is {next_up}."
            if next_up
            else " No further candidate remains in that ranking."
        )
        await self._notify(
            recipient_user_id=allocation.approved_by_user_id,
            message=(
                f"{name} has declined the assignment for "
                f'"{programme.title if programme else "the programme"}" '
                f"({allocation.registry_number}). Reason: {reason}.{follow_on}"
            ),
            notification_type=NotificationType.APPROVAL,
            link_to=f"/allocations/{allocation_id}",
        )
        await self._audit.record(
            AuditAction.ASSIGNMENT_DECLINED,
            entity_type="ALLOCATION",
            entity_id=allocation_id,
            before={"status": AllocationStatus.PENDING_TRAINER.value},
            after={
                "status": AllocationStatus.DECLINED.value,
                "decline_reason": reason,
                "declined_at": now.isoformat(),
            },
            detail=f"{name} declined {allocation.registry_number}: {reason}",
        )
        return await self.get(allocation_id)

    # -------------------------------------------------------------- helpers

    async def _create_allocation(
        self,
        *,
        prediction: Prediction,
        run: PredictionRun,
        programme: TrainingProgramme,
        actor_user_id: int,
        remarks: str,
    ) -> Allocation:
        """Write the allocation row and advance the programme.

        The five frozen columns are copied here and nowhere else, which is what makes
        "the receipt is never recomputed" a property of the code rather than a habit.

        Args:
            prediction: The ranked candidate.
            run: The run it came from, supplying the weights in force.
            programme: The programme, locked by the caller.
            actor_user_id: The approving Administrator.
            remarks: Optional note.

        Returns:
            The flushed allocation.
        """
        registry = await self._next_registry_number("ALL")
        allocation = Allocation(
            registry_number=registry,
            prediction_id=prediction.prediction_id,
            programme_id=programme.programme_id,
            trainer_id=prediction.trainer_id,
            approved_by_user_id=actor_user_id,
            status=AllocationStatus.PENDING_TRAINER.value,
            approval_date=self._clock.now(),
            remarks=remarks or None,
            frozen_score=prediction.prediction_score,
            frozen_rank_position=prediction.rank_position,
            frozen_breakdown=prediction.breakdown,
            frozen_weights=run.weights_snapshot,
            frozen_rationale=prediction.rationale,
            # Derived from the run, not from the request body. A client-supplied flag
            # on a frozen record could be made to say anything.
            weights_were_simulated=not run.weights_are_policy_default,
        )
        self._session.add(allocation)
        await self._session.flush()

        programme.status = ProgrammeStatus.AWAITING_RESPONSE.value
        await self._session.flush()

        await self._notify(
            recipient_user_id=await self._trainer_user_id(prediction.trainer_id),
            message=(
                f'You have been selected to deliver "{programme.title}" '
                f"({programme.start_date:%d %b} - {programme.end_date:%d %b %Y}). "
                f"{prediction.rationale} Please accept or decline."
            ),
            notification_type=NotificationType.ASSIGNMENT,
            link_to=f"/assignments/{allocation.allocation_id}",
        )
        return allocation

    def _check_client_expectations(
        self,
        prediction: Prediction,
        expected_programme_id: int | None,
        expected_trainer_id: int | None,
    ) -> None:
        """Verify optional client-supplied ids agree with the prediction.

        The frontend sends ``programmeId`` and ``trainerId`` alongside ``predictionId``.
        They are not inputs — both are derivable — but disagreeing with them is a real
        signal: it means the screen the operator approved from is not showing what the
        server is about to record.

        Args:
            prediction: The candidate.
            expected_programme_id: What the client believes.
            expected_trainer_id: What the client believes.

        Raises:
            ConflictError: On any disagreement.
        """
        if expected_programme_id is not None and expected_programme_id != prediction.programme_id:
            raise ConflictError(
                "This candidate belongs to a different programme from the one on "
                "screen. Reload the ranking and try again."
            )
        if expected_trainer_id is not None and expected_trainer_id != prediction.trainer_id:
            raise ConflictError(
                "This candidate is not the trainer shown on screen. Reload the ranking "
                "and try again."
            )

    async def _assert_no_live_allocation(self, programme: TrainingProgramme) -> None:
        """Refuse a second allocation on a programme that already has one.

        Args:
            programme: The locked programme.

        Raises:
            ConflictError: If a live allocation exists.
        """
        result = await self._session.execute(
            select(Allocation.registry_number, Allocation.status)
            .where(
                Allocation.programme_id == programme.programme_id,
                Allocation.status.in_(LIVE_STATUSES),
            )
            .limit(1)
        )
        existing = result.one_or_none()
        if existing is not None:
            raise ConflictError(
                f'"{programme.title}" already has an allocation '
                f"({existing.registry_number}, {existing.status}). Withdraw it before "
                "approving another — a course has one trainer."
            )

    async def _requirements(self, programme: TrainingProgramme) -> ProgrammeRequirements:
        """Load the programme into the engine's input type for a gate re-check.

        Args:
            programme: The programme.

        Returns:
            The requirements.

        Raises:
            BusinessRuleViolation: If requirements are undefined (FR-05).
        """
        from app.models.reference import QualificationLevel, SpecializationArea

        if programme.required_specialization_area_id is None:
            raise BusinessRuleViolation(
                "FR-05",
                "This programme has no required specialisation, so there is nothing to "
                "check a candidate against.",
            )
        result = await self._session.execute(
            select(
                SpecializationArea.name,
                SpecializationArea.discipline_group,
            ).where(
                SpecializationArea.specialization_area_id
                == programme.required_specialization_area_id
            )
        )
        area = result.one()
        minimum_order: int | None = None
        minimum_name: str | None = None
        if programme.minimum_qualification_level_id is not None:
            level = await self._session.get(
                QualificationLevel, programme.minimum_qualification_level_id
            )
            if level is not None:
                minimum_order = level.rank_order
                minimum_name = level.name
        return ProgrammeRequirements(
            programme_id=programme.programme_id,
            title=programme.title,
            required_specialization_area_id=programme.required_specialization_area_id,
            required_specialization_name=area.name,
            discipline_group=area.discipline_group,
            minimum_experience=programme.minimum_experience,
            minimum_qualification_order=minimum_order,
            minimum_qualification_name=minimum_name,
            start_date=programme.start_date,
            end_date=programme.end_date,
        )

    async def _live_facts(
        self, programme: TrainingProgramme, trainer_id: int
    ) -> CandidateFacts:
        """Fetch one trainer's current facts through the engine's own query.

        Args:
            programme: The programme being staffed.
            trainer_id: The candidate.

        Returns:
            Their facts as of now.

        Raises:
            NotFoundError: If the trainer no longer exists.
        """
        requirements = await self._requirements(programme)
        repo = TrainerRepository(self._session)
        facts = await repo.fetch_scoring_facts(
            area_id=requirements.required_specialization_area_id,
            discipline_group=requirements.discipline_group,
            programme_id=programme.programme_id,
            start_date=programme.start_date,
            end_date=programme.end_date,
            trainer_ids=[trainer_id],
        )
        if not facts:
            raise NotFoundError("That trainer's record could not be found.")
        return facts[0]

    async def _recheck_gates(
        self, facts: CandidateFacts, programme: TrainingProgramme, trainer_id: int
    ) -> None:
        """Re-apply the hard gates against live data before approving.

        A ranking is a photograph taken at the moment of the run. Between then and now
        a trainer may have declared leave, accepted another course, or been marked
        unavailable. Approving anyway would post an officer to a course they cannot
        attend, and the system would have had the information to prevent it.

        Args:
            facts: The candidate's current facts.
            programme: The programme.
            trainer_id: The candidate, for the log.

        Raises:
            ConflictError: If any gate now fails, quoting the rule.
        """
        exclusion = evaluate_gates(facts, await self._requirements(programme))
        if exclusion is None:
            return
        logger.warning(
            "approval_blocked_by_live_gate",
            trainer_id=trainer_id,
            programme_id=programme.programme_id,
            reason=exclusion.reason.value,
        )
        raise ConflictError(
            f"{facts.rank_code} {facts.full_name} can no longer be assigned to this "
            f"course: {exclusion.reason_detail} "
            f"({exclusion.business_rule.value}). This changed after the ranking was "
            "generated. Approve another candidate, or re-run the prediction."
        )

    async def _candidates_after(self, run_id: int, rank_position: int) -> list[Prediction]:
        """Return the run's candidates below a rank, best first, excluding allocated ones.

        Args:
            run_id: The run being reused.
            rank_position: Promote from below this rank.

        Returns:
            Predictions in rank order.
        """
        result = await self._session.execute(
            select(Prediction)
            .outerjoin(Allocation, Allocation.prediction_id == Prediction.prediction_id)
            .where(
                Prediction.run_id == run_id,
                Prediction.rank_position > rank_position,
                or_(
                    Allocation.allocation_id.is_(None),
                    Allocation.status.not_in(LIVE_STATUSES),
                ),
            )
            .order_by(Prediction.rank_position)
        )
        return list(result.scalars().all())

    async def _peek_next(self, allocation: Allocation) -> str | None:
        """Name the next-ranked candidate, for the decline notification.

        Args:
            allocation: The declined allocation.

        Returns:
            e.g. ``"IP Sarah Mugisha (rank 4)"``, or None if the ranking is exhausted.
        """
        prediction = await self._session.get(Prediction, allocation.prediction_id)
        if prediction is None:  # pragma: no cover
            return None
        result = await self._session.execute(
            select(User.full_name, PoliceRank.code, Prediction.rank_position)
            .join(Trainer, Trainer.trainer_id == Prediction.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .where(
                Prediction.run_id == prediction.run_id,
                Prediction.rank_position > allocation.frozen_rank_position,
            )
            .order_by(Prediction.rank_position)
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return f"{row.code} {row.full_name} (rank {row.rank_position})"

    async def _load(self, allocation_id: int) -> Allocation:
        """Load an allocation or raise."""
        allocation = await self._session.get(Allocation, allocation_id)
        if allocation is None:
            raise NotFoundError("That allocation could not be found.")
        return allocation

    async def _load_own(self, allocation_id: int, trainer_id: int) -> Allocation:
        """Load an allocation, refusing another trainer's (B4, layer 2).

        Args:
            allocation_id: Primary key.
            trainer_id: The caller's trainer id.

        Returns:
            The allocation.

        Raises:
            ForbiddenError: If it belongs to someone else.
        """
        allocation = await self._load(allocation_id)
        if allocation.trainer_id != trainer_id:
            raise ForbiddenError("You may only respond to your own assignments.")
        return allocation

    async def _trainer_user_id(self, trainer_id: int) -> int:
        """Return the user account behind a trainer record."""
        result = await self._session.execute(
            select(Trainer.user_id).where(Trainer.trainer_id == trainer_id)
        )
        return int(result.scalar_one())

    async def _trainer_display(self, trainer_id: int) -> str:
        """Return ``"IP Sarah Mugisha"`` for notification and audit text."""
        result = await self._session.execute(
            select(PoliceRank.code, User.full_name)
            .join(Trainer, Trainer.rank_id == PoliceRank.rank_id)
            .join(User, User.user_id == Trainer.user_id)
            .where(Trainer.trainer_id == trainer_id)
        )
        row = result.one()
        return f"{row.code} {row.full_name}"

    async def _notify(
        self,
        *,
        recipient_user_id: int,
        message: str,
        notification_type: NotificationType,
        link_to: str,
    ) -> None:
        """Queue a notification and remember it for background dispatch.

        Args:
            recipient_user_id: Who to tell.
            message: What to tell them.
            notification_type: The category.
            link_to: Where the notification points.
        """
        notification = await self._notifications.create(
            recipient_user_id=recipient_user_id,
            message=message,
            notification_type=notification_type,
            link_to=link_to,
        )
        self.pending_dispatch.append(notification.notification_id)

    async def _next_registry_number(self, family: str) -> str:
        """Draw a registry number from the database's own sequence (§5.9).

        ``MAX(id) + 1`` would issue duplicates under concurrent approvals, and a
        duplicate registry number on a government record is a serious defect.

        Args:
            family: ``ALL`` or ``EVL``.

        Returns:
            e.g. ``TPS/ALL/2026/0417``.
        """
        from sqlalchemy import text

        result = await self._session.execute(
            text("SELECT next_registry_number(:family)"), {"family": family}
        )
        return str(result.scalar_one())


def breakdown_of(allocation: Allocation) -> list[CriterionScoreRead]:
    """Render a frozen breakdown as response DTOs.

    Args:
        allocation: The allocation.

    Returns:
        The Score Ledger exactly as it was at approval.
    """
    return [CriterionScoreRead.model_validate(item) for item in allocation.frozen_breakdown]
