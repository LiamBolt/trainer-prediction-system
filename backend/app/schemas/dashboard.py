"""Dashboard and report DTOs (§6.9, §6.13)."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import Field

from app.schemas.admin import AuditEntryRead
from app.schemas.allocation import AllocationListItem
from app.schemas.base import CamelModel, OptionalRatingField, ScoreField
from app.schemas.programme import ProgrammeSummary


class Bucket(CamelModel):
    """A labelled count, for a bar or a donut."""

    label: str
    value: float


class TrendPoint(CamelModel):
    """A labelled point on a line."""

    label: str
    value: float


class RuntimePoint(CamelModel):
    """One prediction run's duration, for the System Health chart."""

    date: datetime.datetime
    ms: int


class PredictionQueueItem(CamelModel):
    """A programme with a ranking waiting on a decision."""

    programme_id: int
    title: str
    category: str
    ranked_count: int
    top_trainer_name: str
    top_trainer_rank: str
    top_score: ScoreField
    generated_date: datetime.datetime


class DashboardSummary(CamelModel):
    """The four headline figures every role's dashboard leads with."""

    awaiting_approval: int = 0
    predictions_ready: int = 0
    allocations_this_quarter: int = 0
    evaluations_outstanding: int = 0


class DashboardData(CamelModel):
    """The dashboard, shaped by the caller's role (§6.13).

    **The role comes from the token, never from a parameter.** The frontend currently
    sends `?role=&userId=` — honouring that would let a Trainer request the
    Administrator dashboard, which is conflict B3 in ``PROGRESS.md``.

    Every field beyond ``summary`` is optional and populated only for the roles that
    have a use for it, so one response type serves all four screens without either a
    discriminated union in the client or four near-identical endpoints here.
    """

    role: str
    summary: DashboardSummary

    # Training Administrator
    prediction_queue: list[PredictionQueueItem] | None = None
    utilisation: list[Bucket] | None = None
    performance_trend: list[TrendPoint] | None = None
    recent_activity: list[AuditEntryRead] | None = None

    # Training Officer
    my_requests_by_status: list[Bucket] | None = None
    requests_needing_requirements: list[ProgrammeSummary] | None = None

    # Trainer
    upcoming: list[AllocationListItem] | None = None
    pending_invitations: list[AllocationListItem] | None = None
    profile_completeness: int | None = None
    my_mean_score: OptionalRatingField = None
    my_score_trend: list[TrendPoint] | None = None

    # System Administrator
    users_by_role: list[Bucket] | None = None
    failed_signins24h: int | None = Field(default=None, alias="failedSignins24h")
    locked_accounts: int | None = None
    active_users: int | None = None
    prediction_runtimes: list[RuntimePoint] | None = None
    audit_volume: int | None = None


# --- Reports (FR-11, §6.9) ---------------------------------------------------


class UtilisationRow(CamelModel):
    """One trainer's share of the work.

    The report exists to expose over-reliance on familiar names — the thing a ranking
    system is supposed to correct and can quietly entrench.
    """

    trainer_id: int
    trainer_name: str
    rank: str
    force_number: str
    station: str = ""
    allocations: int
    last_assigned: datetime.datetime | None = None
    mean_score: OptionalRatingField = None


class AllocationHistoryRow(CamelModel):
    """One allocation, as it appears in the history report."""

    allocation_id: int
    registry_number: str
    programme_title: str
    trainer_name: str
    approved_by_name: str
    approval_date: datetime.datetime
    status: str
    score: ScoreField
    evaluation_score: OptionalRatingField = None


class PerformanceTrendRow(CamelModel):
    """Mean evaluation score for one quarter."""

    quarter: str = Field(description="e.g. '2026 Q3'.")
    mean_score: OptionalRatingField = None
    evaluation_count: int


class ReportResponse(CamelModel):
    """A report with the filters that produced it.

    The filters travel with the data so an exported PDF can state its own provenance.
    A report showing figures without saying what it was filtered to is how two people
    end up arguing about numbers that were never comparable.
    """

    rows: list[Any]
    chart: list[TrendPoint] = Field(default_factory=list)
    generated_at: datetime.datetime
    filters: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0


# --- System health (§6.14) ---------------------------------------------------


class PredictionPerformance(CamelModel):
    """Prediction run times against the NFR-01 budget."""

    runs: list[RuntimePoint] = Field(default_factory=list)
    threshold_ms: int = Field(description="NFR-01 allows ten seconds.")
    slowest_ms: int = 0
    mean_ms: int = 0
    breaches: int = Field(default=0, description="Runs that exceeded the threshold.")
    window_days: int = 30


class SecurityHealth(CamelModel):
    """The security figures the System Health screen leads with."""

    failed_signins24h: int = Field(alias="failedSignins24h")
    locked_accounts: int
    unauthorised_attempts24h: int = Field(alias="unauthorisedAttempts24h")
    active_sessions: int
    deactivated_accounts: int
    failed_notifications: int = Field(
        default=0, description="Notifications whose delivery failed — surfaced, not swallowed."
    )
