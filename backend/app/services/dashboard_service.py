"""The role-adaptive dashboard (§6.13). Imports no `fastapi` (B7).

**The role comes from the token.** The frontend calls `GET /dashboard?role=&userId=`,
which lets the caller declare their own role — a Trainer could request the
Administrator dashboard (conflict B3). This service takes the authenticated user and
derives everything from it; there is no parameter to disagree with.

**One round trip per panel group, not nine.** The Administrator's dashboard alone shows
four headline figures, a prediction queue, a utilisation chart, a performance trend, and
recent activity. Fired as separate requests, that is nine round trips over a district's
connection before anything renders. The headline figures come back as a **single row**
from one query of scalar subqueries; the panels are four more.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.enums import (
    AccountStatus,
    AllocationStatus,
    AuditAction,
    ProgrammeStatus,
    RoleName,
)
from app.models.identity import User
from app.models.prediction import Prediction, PredictionRun
from app.models.programme import TrainingProgramme
from app.models.reference import PoliceRank, Role, TrainingCategory
from app.models.system import AuditLog
from app.models.trainer import Trainer
from app.schemas.admin import AuditEntryRead
from app.schemas.auth import UserSummary
from app.schemas.dashboard import (
    Bucket,
    DashboardData,
    DashboardSummary,
    PredictionQueueItem,
    RuntimePoint,
    TrendPoint,
)
from app.schemas.programme import ProgrammeSummary
from app.services.allocation_service import AllocationService
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

#: How many rows each dashboard panel shows. A dashboard is a summary; a panel that
#: scrolls is a report that has escaped onto the wrong screen.
PANEL_LIMIT = 8


class DashboardService:
    """Builds the dashboard for whoever is asking.

    Args:
        session: The request's session.
        clock: Injected clock, so "this quarter" is testable.
    """

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def build(self, user: UserSummary) -> DashboardData:
        """Build the dashboard for the authenticated user (§6.13).

        Args:
            user: The caller, from the token.

        Returns:
            The panels their role can see, and no others.
        """
        summary = await self._summary()
        data = DashboardData(role=user.role, summary=summary)

        if user.role == RoleName.TRAINING_ADMINISTRATOR:
            data.prediction_queue = await self._prediction_queue()
            data.utilisation = await self._utilisation()
            data.performance_trend = await self._performance_trend()
            data.recent_activity = await self._recent_activity()
        elif user.role == RoleName.TRAINING_OFFICER:
            data.my_requests_by_status = await self._requests_by_status(user.user_id)
            data.requests_needing_requirements = await self._needing_requirements(user.user_id)
        elif user.role == RoleName.TRAINER:
            await self._trainer_panels(data, user)
        elif user.role == RoleName.SYSTEM_ADMINISTRATOR:
            data.users_by_role = await self._users_by_role()
            data.failed_signins24h = await self._audit_count_since(AuditAction.LOGIN_FAILED, 1)
            data.locked_accounts = await self._locked_accounts()
            data.active_users = await self._active_users()
            data.prediction_runtimes = await self._prediction_runtimes()
            data.audit_volume = await self._audit_volume()

        return data

    # ----------------------------------------------------------- headline

    async def _summary(self) -> DashboardSummary:
        """Return the four headline figures in **one** query.

        Four scalar subqueries in a single `SELECT` rather than four round trips. The
        figures are read together and shown together; fetching them separately would
        also let them disagree by however long the requests took.

        Returns:
            The headline figures.
        """
        quarter_start = self._quarter_start()
        result = await self._session.execute(
            select(
                select(func.count())
                .select_from(Allocation)
                .where(Allocation.status == AllocationStatus.PENDING_TRAINER.value)
                .scalar_subquery()
                .label("awaiting_approval"),
                select(func.count())
                .select_from(TrainingProgramme)
                .where(TrainingProgramme.status == ProgrammeStatus.PREDICTED.value)
                .scalar_subquery()
                .label("predictions_ready"),
                select(func.count())
                .select_from(Allocation)
                .where(Allocation.approval_date >= quarter_start)
                .scalar_subquery()
                .label("allocations_this_quarter"),
                select(func.count())
                .select_from(Allocation)
                .where(Allocation.status == AllocationStatus.CONDUCTED.value)
                .scalar_subquery()
                .label("evaluations_outstanding"),
            )
        )
        row = result.one()
        return DashboardSummary.model_validate(row)

    # ---------------------------------------------- Training Administrator

    async def _prediction_queue(self) -> list[PredictionQueueItem]:
        """Rankings waiting on a decision, best candidate named.

        Returns:
            Programmes at `PREDICTED` with a live run, newest first.
        """
        result = await self._session.execute(
            select(
                TrainingProgramme.programme_id,
                TrainingProgramme.title,
                TrainingCategory.name.label("category"),
                PredictionRun.ranked_count,
                User.full_name.label("top_trainer_name"),
                PoliceRank.code.label("top_trainer_rank"),
                Prediction.prediction_score.label("top_score"),
                PredictionRun.generated_at.label("generated_date"),
            )
            .join(PredictionRun, PredictionRun.programme_id == TrainingProgramme.programme_id)
            .join(
                TrainingCategory,
                TrainingCategory.category_id == TrainingProgramme.category_id,
            )
            .join(
                Prediction,
                (Prediction.run_id == PredictionRun.run_id) & (Prediction.rank_position == 1),
            )
            .join(Trainer, Trainer.trainer_id == Prediction.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .where(
                TrainingProgramme.status == ProgrammeStatus.PREDICTED.value,
                PredictionRun.is_superseded.is_(False),
            )
            .order_by(PredictionRun.generated_at.desc())
            .limit(PANEL_LIMIT)
        )
        return [PredictionQueueItem.model_validate(row) for row in result.all()]

    async def _utilisation(self) -> list[Bucket]:
        """Who is carrying the work.

        The chart exists to expose over-reliance on a handful of familiar names — the
        thing a ranking system is meant to correct and can quietly entrench.

        Returns:
            The busiest trainers by allocation count.
        """
        result = await self._session.execute(
            select(
                func.concat(PoliceRank.code, " ", User.full_name).label("label"),
                func.count(Allocation.allocation_id).label("value"),
            )
            .join(Trainer, Trainer.trainer_id == Allocation.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .group_by(PoliceRank.code, User.full_name)
            .order_by(func.count(Allocation.allocation_id).desc())
            .limit(PANEL_LIMIT)
        )
        return [Bucket(label=row.label, value=float(row.value)) for row in result.all()]

    async def _performance_trend(self) -> list[TrendPoint]:
        """Mean evaluation score by quarter.

        Returns:
            The last eight quarters, oldest first.
        """
        quarter = func.concat(
            cast(func.extract("year", PerformanceEvaluation.evaluation_date), Integer),
            " Q",
            cast(func.extract("quarter", PerformanceEvaluation.evaluation_date), Integer),
        )
        result = await self._session.execute(
            select(
                quarter.label("label"),
                func.round(func.avg(PerformanceEvaluation.score_awarded), 2).label("value"),
                func.min(PerformanceEvaluation.evaluation_date).label("sort_key"),
            )
            .group_by(quarter)
            .order_by(func.min(PerformanceEvaluation.evaluation_date).desc())
            .limit(8)
        )
        rows = list(result.all())
        rows.reverse()
        return [TrendPoint(label=row.label, value=float(row.value or 0)) for row in rows]

    async def _recent_activity(self) -> list[AuditEntryRead]:
        """The last few things that happened, from the audit log.

        Read from `audit_logs` rather than a separate activity feed: the entries already
        exist, are append-only, and are what an investigator would consult. A second
        feed could disagree with them.

        Returns:
            Recent decisions, newest first.
        """
        result = await self._session.execute(
            select(
                AuditLog.log_id,
                AuditLog.actor_user_id,
                User.full_name.label("actor_name"),
                AuditLog.actor_role,
                AuditLog.action,
                AuditLog.entity_type,
                AuditLog.entity_id,
                AuditLog.detail,
                AuditLog.created_at,
            )
            .outerjoin(User, User.user_id == AuditLog.actor_user_id)
            .where(
                AuditLog.action.in_(
                    (
                        AuditAction.ALLOCATION_APPROVED.value,
                        AuditAction.ASSIGNMENT_ACCEPTED.value,
                        AuditAction.ASSIGNMENT_DECLINED.value,
                        AuditAction.EVALUATION_RECORDED.value,
                        AuditAction.PREDICTION_GENERATED.value,
                        AuditAction.PROGRAMME_CREATED.value,
                    )
                )
            )
            .order_by(AuditLog.created_at.desc())
            .limit(PANEL_LIMIT)
        )
        return [AuditEntryRead.model_validate(row) for row in result.all()]

    # --------------------------------------------------- Training Officer

    async def _requests_by_status(self, user_id: int) -> list[Bucket]:
        """The caller's own requests, grouped by where they have reached.

        Args:
            user_id: The officer.

        Returns:
            One bucket per status.
        """
        result = await self._session.execute(
            select(
                TrainingProgramme.status.label("label"),
                func.count().label("value"),
            )
            .where(TrainingProgramme.created_by_user_id == user_id)
            .group_by(TrainingProgramme.status)
            .order_by(func.count().desc())
        )
        return [Bucket(label=row.label, value=float(row.value)) for row in result.all()]

    async def _needing_requirements(self, user_id: int) -> list[ProgrammeSummary]:
        """The caller's drafts that cannot be predicted yet (FR-05).

        Args:
            user_id: The officer.

        Returns:
            Their programmes still at `DRAFT`.
        """
        from app.services.programme_service import ProgrammeService

        service = ProgrammeService(self._session, AuditService(self._session), self._clock)
        result = await self._session.execute(
            service.list_query()
            .where(
                TrainingProgramme.created_by_user_id == user_id,
                TrainingProgramme.status == ProgrammeStatus.DRAFT.value,
            )
            .order_by(TrainingProgramme.start_date)
            .limit(PANEL_LIMIT)
        )
        return [ProgrammeSummary.model_validate(row) for row in result.all()]

    # ------------------------------------------------------------ Trainer

    async def _trainer_panels(self, data: DashboardData, user: UserSummary) -> None:
        """Populate the Trainer's panels.

        Args:
            data: The dashboard being built, mutated in place.
            user: The caller.
        """
        if user.trainer_id is None:
            # A Trainer account with no profile is a broken state the user service now
            # makes impossible to create. An older account could still be in it, and a
            # dashboard that raises is worse than one that shows nothing.
            return

        allocations = AllocationService(
            self._session,
            AuditService(self._session),
            NotificationService(self._session, self._clock),
            self._clock,
        )
        grouped = await allocations.assignments_for(user.trainer_id)
        data.pending_invitations = grouped["pending"]
        data.upcoming = grouped["upcoming"]

        completeness = await self._session.execute(
            select(Trainer.profile_completeness).where(Trainer.trainer_id == user.trainer_id)
        )
        data.profile_completeness = completeness.scalar_one_or_none()

        scores = await self._session.execute(
            select(
                PerformanceEvaluation.score_awarded,
                PerformanceEvaluation.evaluation_date,
            )
            .where(PerformanceEvaluation.trainer_id == user.trainer_id)
            .order_by(PerformanceEvaluation.evaluation_date)
        )
        rows = list(scores.all())
        if rows:
            total = sum((row.score_awarded for row in rows), Decimal("0"))
            data.my_mean_score = total / Decimal(len(rows))
            data.my_score_trend = [
                TrendPoint(label=row.evaluation_date.strftime("%b %Y"), value=float(row.score_awarded))
                for row in rows[-8:]
            ]

    # ----------------------------------------------- System Administrator

    async def _users_by_role(self) -> list[Bucket]:
        """Active accounts per role."""
        result = await self._session.execute(
            select(Role.display_name.label("label"), func.count(User.user_id).label("value"))
            .outerjoin(User, (User.role_id == Role.role_id))
            .group_by(Role.display_name)
            .order_by(func.count(User.user_id).desc())
        )
        return [Bucket(label=row.label, value=float(row.value)) for row in result.all()]

    async def _audit_count_since(self, action: AuditAction, days: int) -> int:
        """Count one audit action within a recent window.

        Args:
            action: Which action.
            days: How far back.

        Returns:
            The count.
        """
        since = self._clock.now() - datetime.timedelta(days=days)
        result = await self._session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == action.value, AuditLog.created_at >= since)
        )
        return int(result.scalar_one())

    async def _locked_accounts(self) -> int:
        """Count accounts currently locked out (FR-01)."""
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .where(User.locked_until.is_not(None), User.locked_until > self._clock.now())
        )
        return int(result.scalar_one())

    async def _active_users(self) -> int:
        """Count accounts that can sign in."""
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .where(User.account_status == AccountStatus.ACTIVE.value)
        )
        return int(result.scalar_one())

    async def _prediction_runtimes(self) -> list[RuntimePoint]:
        """Recent prediction durations, for the NFR-01 chart."""
        result = await self._session.execute(
            select(PredictionRun.generated_at, PredictionRun.elapsed_ms)
            .order_by(PredictionRun.generated_at.desc())
            .limit(30)
        )
        rows = list(result.all())
        rows.reverse()
        return [RuntimePoint(date=row.generated_at, ms=row.elapsed_ms) for row in rows]

    async def _audit_volume(self) -> int:
        """Count audit entries written in the last 24 hours."""
        since = self._clock.now() - datetime.timedelta(days=1)
        result = await self._session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since)
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------ helpers

    def _quarter_start(self) -> datetime.datetime:
        """Return midnight on the first day of the current quarter.

        Returns:
            A timezone-aware datetime.
        """
        now = self._clock.now()
        first_month = 3 * ((now.month - 1) // 3) + 1
        return now.replace(
            month=first_month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
