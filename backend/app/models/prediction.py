"""Prediction domain — runs, ranked predictions, and the Exclusion Ledger (§5.6)."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import JsonB, Score
from app.models.enums import BusinessRule, ConfidenceBand, ExclusionReason, check_in

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.programme import TrainingProgramme
    from app.models.scoring import ScoringPolicy
    from app.models.trainer import Trainer


class PredictionRun(Base, TimestampMixin):
    """One execution of the prediction engine against one programme.

    Serves FR-06 (generate a ranked list) and NFR-01 (performance).

    Re-running a prediction **does not delete the previous run** — it sets
    ``is_superseded`` on it. What the system recommended, and when, is part of the
    audit record: an officer must be able to explain a decision taken against a
    ranking that has since been regenerated.

    ``weights_snapshot`` freezes the exact weights used. Reading them back from
    ``scoring_policies`` later would show today's policy, not the one that produced
    this ranking, and would silently rewrite history the first time a weight changed.

    ``elapsed_ms`` is recorded on every run (NFR-01), which is what makes performance
    degradation visible as a trend rather than as a complaint.
    """

    __tablename__ = "prediction_runs"
    __table_args__ = (
        CheckConstraint("candidate_pool_size >= 0", name="candidate_pool_size_non_negative"),
        CheckConstraint("excluded_count >= 0", name="excluded_count_non_negative"),
        CheckConstraint("ranked_count >= 0", name="ranked_count_non_negative"),
        CheckConstraint("elapsed_ms >= 0", name="elapsed_ms_non_negative"),
        CheckConstraint(
            "excluded_count + ranked_count <= candidate_pool_size",
            name="counts_within_pool",
        ),
        Index("ix_prediction_runs_programme_generated", "programme_id", "generated_at"),
        Index("ix_prediction_runs_generated_at", "generated_at"),
        Index("ix_prediction_runs_policy_id", "policy_id"),
        Index("ix_prediction_runs_generated_by_user_id", "generated_by_user_id"),
        {"comment": "One row per prediction engine execution. Superseded, never deleted."},
    )

    run_id: Mapped[int] = primary_key()
    programme_id: Mapped[int] = mapped_column(
        ForeignKey("training_programmes.programme_id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("scoring_policies.policy_id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL when run with ad-hoc simulated weights rather than a saved policy.",
    )
    weights_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JsonB,
        nullable=False,
        comment="The exact weights used, frozen. Never re-read from scoring_policies.",
    )
    weights_are_policy_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="False when the Administrator simulated weights in the Weight Studio.",
    )
    candidate_pool_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Trainers considered before any gate was applied."
    )
    excluded_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Trainers removed by the BR-03/BR-04/FR-05 gates."
    )
    ranked_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Trainers that passed every gate and were scored."
    )
    elapsed_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Wall-clock duration. NFR-01: measured on every run."
    )
    is_superseded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Set when a later run replaces this one. The row itself is never deleted.",
    )
    generated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    programme: Mapped[TrainingProgramme] = relationship(lazy="raise_on_sql")
    policy: Mapped[ScoringPolicy | None] = relationship(lazy="raise_on_sql")
    generated_by: Mapped[User] = relationship(lazy="raise_on_sql")
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="raise_on_sql"
    )
    exclusions: Mapped[list[PredictionExclusion]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="raise_on_sql"
    )


class Prediction(Base):
    """One trainer's score and rank within one run.

    Serves FR-06 and FR-07 (the Score Ledger).

    ``UNIQUE(run_id, rank_position)`` is not decoration. It is what stops a bug in the
    tie-break comparator from silently producing two trainers ranked first — a defect
    that would be invisible in the UI and indefensible in an audit.

    ``breakdown`` holds the ``CriterionScore[]`` array driving the frontend's Score
    Ledger. It is JSONB rather than a child table because it is written once and read
    as a unit; normalising it would add a join to every read for no query benefit. A
    GIN index is deliberately **not** added — no query searches inside it, and an
    unused index is write cost with no read benefit (§9).

    No ``updated_at``: a prediction is an immutable record of what the engine produced
    at a moment in time. Re-running produces a new run, not an edit.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("run_id", "trainer_id", name="uq_predictions_run_id_trainer_id"),
        UniqueConstraint("run_id", "rank_position", name="uq_predictions_run_id_rank_position"),
        CheckConstraint(check_in("confidence_band", ConfidenceBand), name="confidence_band_valid"),
        CheckConstraint(
            "prediction_score >= 0 AND prediction_score <= 100", name="prediction_score_range"
        ),
        CheckConstraint(
            "confidence_level >= 0 AND confidence_level <= 100", name="confidence_level_range"
        ),
        CheckConstraint("rank_position > 0", name="rank_position_positive"),
        Index("ix_predictions_run_rank", "run_id", "rank_position"),
        Index("ix_predictions_trainer_id", "trainer_id"),
        Index("ix_predictions_programme_id", "programme_id"),
        {"comment": "A trainer's score and rank within a run. Immutable; no updated_at."},
    )

    prediction_id: Mapped[int] = primary_key()
    run_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    programme_id: Mapped[int] = mapped_column(
        ForeignKey("training_programmes.programme_id", ondelete="CASCADE"),
        nullable=False,
        comment="Denormalised from the run so programme-scoped queries skip a join.",
    )
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="RESTRICT"),
        nullable=False,
        comment="RESTRICT: a scored trainer forms part of a decision record.",
    )
    prediction_score: Mapped[Decimal] = mapped_column(
        Score, nullable=False, comment="0-100 weighted total, one decimal place in practice."
    )
    confidence_level: Mapped[Decimal] = mapped_column(
        Score,
        nullable=False,
        comment="0-100 data completeness, NOT statistical confidence. See ConfidenceBand.",
    )
    confidence_band: Mapped[str] = mapped_column(String(10), nullable=False)
    rank_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1 = best. Unique within a run."
    )
    breakdown: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonB,
        nullable=False,
        comment="CriterionScore[] driving the Score Ledger. Frozen at generation.",
    )
    rationale: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Generated plain-English justification (FR-07)."
    )
    counterfactual: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "The smallest single change that would lift this trainer to rank 1. NULL "
            "when no single change closes the gap — never invented."
        ),
    )
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[PredictionRun] = relationship(back_populates="predictions", lazy="raise_on_sql")
    trainer: Mapped[Trainer] = relationship(lazy="raise_on_sql")
    programme: Mapped[TrainingProgramme] = relationship(lazy="raise_on_sql")


class PredictionExclusion(Base):
    """A trainer removed by a hard gate, and the rule that removed them.

    The Exclusion Ledger. This table is why the system can answer "why isn't
    so-and-so on the list?" without a phone call, and it is the part of the schema
    that most directly addresses the SRS problem statement — allocation decisions that
    cannot be explained.

    ``business_rule`` records the citation (``BR-03``, ``BR-04``, ``FR-05``) so the
    answer is a rule reference rather than an opinion.

    No ``updated_at``: like a prediction, an exclusion is a statement about one moment.
    """

    __tablename__ = "prediction_exclusions"
    __table_args__ = (
        UniqueConstraint("run_id", "trainer_id", name="uq_prediction_exclusions_run_id_trainer_id"),
        CheckConstraint(check_in("reason", ExclusionReason), name="reason_valid"),
        CheckConstraint(check_in("business_rule", BusinessRule), name="business_rule_valid"),
        Index("ix_prediction_exclusions_run_reason", "run_id", "reason"),
        Index("ix_prediction_exclusions_trainer_id", "trainer_id"),
        {"comment": "The Exclusion Ledger: every gated-out trainer, and the rule that gated them."},
    )

    exclusion_id: Mapped[int] = primary_key()
    run_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(
        String(40), nullable=False, comment="Machine reason, one of ExclusionReason."
    )
    reason_detail: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        comment="Human sentence, e.g. 'Assigned to Digital Forensics Level 2 - 10-21 Aug 2026'.",
    )
    business_rule: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Rule citation: BR-03, BR-04, or FR-05."
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[PredictionRun] = relationship(back_populates="exclusions", lazy="raise_on_sql")
    trainer: Mapped[Trainer] = relationship(lazy="raise_on_sql")
