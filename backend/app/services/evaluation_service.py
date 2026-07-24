"""Performance evaluations (FR-10). Imports no `fastapi` (B7).

Recording an evaluation is the one action in this system that changes future
predictions: the PERFORMANCE criterion reads these rows on every run, so a score
entered today alters how this trainer ranks tomorrow. The response says so in plain
language, because an administrator typing a number should know what it does.

Two rules are enforced here and backed by the schema:

- **409 unless the allocation is `CONDUCTED`.** A score for training nobody has
  confirmed took place is not an evaluation.
- **One evaluation per allocation**, enforced by a ``UNIQUE`` constraint. A second
  attempt is a 409, never a silent overwrite — a rating that can be quietly revised is
  not a record.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import ConflictError, NotFoundError
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.enums import (
    AllocationStatus,
    AuditAction,
    AvailabilityStatus,
    NotificationType,
    ProgrammeStatus,
)
from app.models.identity import User
from app.models.programme import TrainingProgramme
from app.models.reference import PoliceRank
from app.models.trainer import Trainer
from app.schemas.allocation import AllocationListItem
from app.schemas.evaluation import EvaluationInput, EvaluationRead, EvaluationsResponse
from app.services.allocation_service import AllocationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class EvaluationService:
    """Records and reads performance evaluations.

    Args:
        session: The request's session.
        audit: Audit service sharing the transaction (B8).
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
        self.pending_dispatch: list[int] = []

    def _base_query(self) -> Select[Any]:
        """Build the projection every evaluation read shares."""
        return (
            select(
                PerformanceEvaluation.evaluation_id,
                PerformanceEvaluation.registry_number,
                PerformanceEvaluation.allocation_id,
                PerformanceEvaluation.trainer_id,
                User.full_name.label("trainer_name"),
                PerformanceEvaluation.programme_id,
                TrainingProgramme.title.label("programme_title"),
                PerformanceEvaluation.score_awarded,
                PerformanceEvaluation.evaluator_comments,
                PerformanceEvaluation.evaluated_by_user_id.label("evaluated_by"),
                PerformanceEvaluation.evaluation_date,
            )
            .join(Trainer, Trainer.trainer_id == PerformanceEvaluation.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(
                TrainingProgramme,
                TrainingProgramme.programme_id == PerformanceEvaluation.programme_id,
            )
        )

    async def _read(self, evaluation_id: int) -> EvaluationRead:
        """Load one evaluation as a DTO.

        Args:
            evaluation_id: Primary key.

        Returns:
            The evaluation.

        Raises:
            NotFoundError: If it does not exist.
        """
        evaluator = User.__table__.alias("evaluator")
        query = (
            self._base_query()
            .add_columns(evaluator.c.full_name.label("evaluated_by_name"))
            .join(
                evaluator,
                evaluator.c.user_id == PerformanceEvaluation.evaluated_by_user_id,
            )
            .where(PerformanceEvaluation.evaluation_id == evaluation_id)
        )
        result = await self._session.execute(query)
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("That evaluation could not be found.")
        return EvaluationRead.model_validate(row)

    async def record(self, payload: EvaluationInput, actor_user_id: int) -> tuple[EvaluationRead, str]:
        """Record a performance evaluation (FR-10).

        Implements FR-10 and the `CONDUCTED` precondition from §6.8.

        Args:
            payload: The score, comments, and date.
            actor_user_id: The recording Administrator.

        Returns:
            The evaluation and a plain-language statement of its consequence.

        Raises:
            NotFoundError: If the allocation does not exist.
            ConflictError: If the training is not yet CONDUCTED, or a score already
                exists for this allocation.
        """
        allocation = await self._session.get(Allocation, payload.allocation_id)
        if allocation is None:
            raise NotFoundError("That allocation could not be found.")

        if allocation.status not in (AllocationStatus.CONDUCTED, AllocationStatus.EVALUATED):
            raise ConflictError(
                f"This allocation is at {allocation.status}. A performance evaluation "
                "can only be recorded once the training has been marked as conducted — "
                "a score for training nobody has confirmed took place is not an "
                "evaluation."
            )

        existing = await self._session.execute(
            select(PerformanceEvaluation.evaluation_id).where(
                PerformanceEvaluation.allocation_id == payload.allocation_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                "This allocation has already been evaluated. A recorded score is part "
                "of the trainer's history and is not revised in place."
            )

        registry = await self._next_registry_number()
        evaluation = PerformanceEvaluation(
            registry_number=registry,
            allocation_id=allocation.allocation_id,
            # Denormalised from the allocation deliberately — see the model docstring.
            # Safe because an allocation's trainer and programme never change.
            trainer_id=allocation.trainer_id,
            programme_id=allocation.programme_id,
            score_awarded=payload.score_awarded,
            evaluator_comments=payload.evaluator_comments,
            evaluated_by_user_id=actor_user_id,
            evaluation_date=payload.evaluation_date,
        )
        self._session.add(evaluation)
        await self._session.flush()

        allocation.status = AllocationStatus.EVALUATED.value
        programme = await self._session.get(TrainingProgramme, allocation.programme_id)
        if programme is not None:
            programme.status = ProgrammeStatus.EVALUATED.value

        # The course is over; release the trainer back into the pool so the
        # AVAILABILITY criterion stops treating them as committed.
        trainer = await self._session.get(Trainer, allocation.trainer_id)
        if trainer is not None and trainer.availability_status == AvailabilityStatus.ASSIGNED:
            trainer.availability_status = AvailabilityStatus.AVAILABLE.value
        await self._session.flush()

        display = await self._trainer_display(allocation.trainer_id)
        message = (
            f"Recorded. This score now informs future rankings for {display}."
        )

        notification = await self._notifications.create(
            recipient_user_id=await self._trainer_user_id(allocation.trainer_id),
            message=(
                f'Your performance on "{programme.title if programme else "the course"}" '
                f"has been evaluated: {payload.score_awarded} out of 5.0. "
                f"{payload.evaluator_comments}"
            ),
            notification_type=NotificationType.EVALUATION,
            link_to="/my-performance",
        )
        self.pending_dispatch.append(notification.notification_id)

        await self._audit.record(
            AuditAction.EVALUATION_RECORDED,
            entity_type="PERFORMANCE_EVALUATION",
            entity_id=evaluation.evaluation_id,
            after={
                "registry_number": registry,
                "allocation_id": allocation.allocation_id,
                "trainer_id": allocation.trainer_id,
                "score_awarded": str(payload.score_awarded),
                "evaluation_date": payload.evaluation_date.isoformat(),
            },
            detail=(
                f"{display} scored {payload.score_awarded}/5.0 on "
                f'"{programme.title if programme else "a course"}" ({registry}). '
                "This score enters the PERFORMANCE criterion for future rankings."
            ),
        )
        return await self._read(evaluation.evaluation_id), message

    async def listing(self, *, recorded_limit: int = 200) -> EvaluationsResponse:
        """Return what is owed and what is done (§6.8).

        ``awaiting`` is unbounded on purpose — it is a backlog, and a truncated backlog
        is a hidden one. ``recorded`` grows without limit over the system's life, so it
        is capped at the most recent entries; the full history is reachable per trainer
        via ``/evaluations/trainer/{id}`` and in the reports.

        Args:
            recorded_limit: How many recorded evaluations to return, newest first.

        Returns:
            Allocations awaiting a score, and evaluations already recorded.
        """
        allocations = AllocationService(
            self._session, self._audit, self._notifications, self._clock
        )
        awaiting_rows = await self._session.execute(
            allocations.list_query()
            .where(Allocation.status == AllocationStatus.CONDUCTED.value)
            .order_by(Allocation.approval_date)
        )
        evaluator = User.__table__.alias("evaluator")
        recorded_rows = await self._session.execute(
            self._base_query()
            .add_columns(evaluator.c.full_name.label("evaluated_by_name"))
            .join(
                evaluator,
                evaluator.c.user_id == PerformanceEvaluation.evaluated_by_user_id,
            )
            .order_by(PerformanceEvaluation.evaluation_date.desc())
            .limit(recorded_limit)
        )
        return EvaluationsResponse(
            awaiting=[AllocationListItem.model_validate(row) for row in awaiting_rows.all()],
            recorded=[EvaluationRead.model_validate(row) for row in recorded_rows.all()],
        )

    async def get(self, evaluation_id: int) -> EvaluationRead:
        """Return one evaluation.

        Args:
            evaluation_id: Primary key.

        Returns:
            The evaluation.
        """
        return await self._read(evaluation_id)

    async def for_trainer(self, trainer_id: int) -> tuple[list[EvaluationRead], Decimal | None]:
        """Return a trainer's evaluation history and its mean.

        Args:
            trainer_id: The trainer.

        Returns:
            The evaluations, newest first, and their arithmetic mean.
        """
        evaluator = User.__table__.alias("evaluator")
        result = await self._session.execute(
            self._base_query()
            .add_columns(evaluator.c.full_name.label("evaluated_by_name"))
            .join(
                evaluator,
                evaluator.c.user_id == PerformanceEvaluation.evaluated_by_user_id,
            )
            .where(PerformanceEvaluation.trainer_id == trainer_id)
            .order_by(PerformanceEvaluation.evaluation_date.desc())
        )
        evaluations = [EvaluationRead.model_validate(row) for row in result.all()]
        if not evaluations:
            return [], None
        # Decimal throughout: a mean of ratings is arithmetic on money-like values, and
        # float would introduce a rounding error into a figure shown to a trainer (B10).
        total = sum((e.score_awarded for e in evaluations), Decimal("0"))
        return evaluations, total / Decimal(len(evaluations))

    async def _trainer_user_id(self, trainer_id: int) -> int:
        """Return the user account behind a trainer record."""
        result = await self._session.execute(
            select(Trainer.user_id).where(Trainer.trainer_id == trainer_id)
        )
        return int(result.scalar_one())

    async def _trainer_display(self, trainer_id: int) -> str:
        """Return ``"IP Sarah Mugisha"`` for the consequence sentence."""
        result = await self._session.execute(
            select(PoliceRank.code, User.full_name)
            .join(Trainer, Trainer.rank_id == PoliceRank.rank_id)
            .join(User, User.user_id == Trainer.user_id)
            .where(Trainer.trainer_id == trainer_id)
        )
        row = result.one()
        return f"{row.code} {row.full_name}"

    async def _next_registry_number(self) -> str:
        """Draw an ``EVL`` registry number from the database sequence (§5.9)."""
        from sqlalchemy import text

        result = await self._session.execute(
            text("SELECT next_registry_number(:family)"), {"family": "EVL"}
        )
        return str(result.scalar_one())


async def count_awaiting(session: AsyncSession) -> int:
    """Count allocations conducted but not yet evaluated.

    Args:
        session: A session.

    Returns:
        How many scores are outstanding.
    """
    result = await session.execute(
        select(func.count())
        .select_from(Allocation)
        .where(Allocation.status == AllocationStatus.CONDUCTED.value)
    )
    return int(result.scalar_one())
