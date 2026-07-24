"""Allocation and evaluation — the decision record (§5.7)."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import JsonB, Rating, Score
from app.models.enums import AllocationStatus, check_in

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.prediction import Prediction
    from app.models.programme import TrainingProgramme
    from app.models.trainer import Trainer


class Allocation(Base, TimestampMixin):
    """An approved assignment of a trainer to a programme.

    Serves FR-08 (approve an allocation) and FR-09 (trainer accepts or declines).

    **A Prediction is not an Allocation** (D7). They are separate tables joined by a
    ``UNIQUE`` constraint on ``prediction_id``, giving a one-to-zero-or-one
    relationship: most predictions never become allocations, and the ones that do not
    must survive as history. Collapsing them into one table with a nullable
    ``approved_at`` would make "the ranking" and "the decision" the same row, and
    deleting a stale ranking would delete a government decision.

    **Why the score is frozen.** The Decision Receipt must show what the Administrator
    actually saw at the moment they approved. If it re-derived the score on read, an
    evaluation recorded next month would silently rewrite the justification for a
    decision taken today. Freezing is the difference between an audit record and a
    rendering. Five columns carry the snapshot: ``frozen_score``,
    ``frozen_rank_position``, ``frozen_breakdown``, ``frozen_weights``, and
    ``frozen_rationale``.

    ``frozen_rationale`` and ``weights_were_simulated`` are required by
    ``frontend/src/types/domain.ts`` but absent from §5.7's column list — recorded as
    conflict C5 in ``PROGRESS.md``.
    """

    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint(check_in("status", AllocationStatus), name="status_valid"),
        # FR-09 requires a reason for a decline, so the database refuses the
        # alternative rather than trusting a form validator.
        CheckConstraint(
            "status <> 'DECLINED' OR decline_reason IS NOT NULL",
            name="declined_requires_reason",
        ),
        CheckConstraint(
            "status <> 'DECLINED' OR declined_at IS NOT NULL",
            name="declined_requires_timestamp",
        ),
        CheckConstraint("frozen_score >= 0 AND frozen_score <= 100", name="frozen_score_range"),
        CheckConstraint("frozen_rank_position > 0", name="frozen_rank_position_positive"),
        Index("ix_allocations_programme_id", "programme_id"),
        Index("ix_allocations_trainer_id", "trainer_id"),
        Index("ix_allocations_status", "status"),
        Index("ix_allocations_approved_by_user_id", "approved_by_user_id"),
        Index("ix_allocations_superseded_by_allocation_id", "superseded_by_allocation_id"),
        # The utilisation report and the AVAILABILITY criterion both ask "how many
        # allocations does this trainer hold, and when was the last?".
        Index("ix_allocations_trainer_approval_date", "trainer_id", "approval_date"),
        {"comment": "Approved trainer assignments with a frozen decision snapshot. FR-08, FR-09."},
    )

    allocation_id: Mapped[int] = primary_key()
    registry_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        comment="e.g. 'TPS/ALL/2026/0417'. From next_registry_number('ALL').",
    )
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.prediction_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="D7: UNIQUE gives one-to-zero-or-one. One prediction, at most one allocation.",
    )
    programme_id: Mapped[int] = mapped_column(
        ForeignKey("training_programmes.programme_id", ondelete="RESTRICT"), nullable=False
    )
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        comment="The Training Administrator accountable for this decision.",
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    approval_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    remarks: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Administrator's note. NULL when none was given."
    )

    frozen_score: Mapped[Decimal] = mapped_column(
        Score, nullable=False, comment="prediction_score as it stood at approval."
    )
    frozen_rank_position: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="rank_position as it stood at approval."
    )
    frozen_breakdown: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonB, nullable=False, comment="CriterionScore[] as shown on the Decision Receipt."
    )
    frozen_weights: Mapped[dict[str, Any]] = mapped_column(
        JsonB, nullable=False, comment="The weights in force at approval."
    )
    frozen_rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The rationale as it stood at approval — this is the text shown to the trainer.",
    )
    weights_were_simulated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True when approved against Weight Studio weights rather than the active policy.",
    )

    decline_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Required when status = DECLINED, enforced by CHECK (FR-09)."
    )
    declined_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the trainer answered. NULL means still awaiting a response.",
    )
    superseded_by_allocation_id: Mapped[int | None] = mapped_column(
        ForeignKey("allocations.allocation_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Set when a decline promotes the next candidate, linking the chain of decisions.",
    )

    prediction: Mapped[Prediction] = relationship(lazy="raise_on_sql")
    programme: Mapped[TrainingProgramme] = relationship(lazy="raise_on_sql")
    trainer: Mapped[Trainer] = relationship(lazy="raise_on_sql")
    approved_by: Mapped[User] = relationship(lazy="raise_on_sql")
    superseded_by: Mapped[Allocation | None] = relationship(
        remote_side="Allocation.allocation_id", lazy="raise_on_sql"
    )


class PerformanceEvaluation(Base, TimestampMixin):
    """A rating awarded to a trainer after delivering a course.

    Serves FR-10 (record performance) and closes the SRS feedback loop: an evaluation
    recorded today changes tomorrow's PERFORMANCE criterion.

    ``trainer_id`` and ``programme_id`` are **deliberately denormalised** from the
    allocation. This table is read on *every* prediction run, once per candidate, to
    compute the PERFORMANCE criterion and its relevance test. Reaching them through
    ``allocation_id`` would add a join to the hottest read path in the system. The
    redundancy is safe because an allocation's trainer and programme never change —
    a reassignment is a new allocation, not an edit — so the copies cannot drift.
    This is one of exactly two intentional denormalisations in the schema (§9).
    """

    __tablename__ = "performance_evaluations"
    __table_args__ = (
        CheckConstraint(
            "score_awarded >= 1.0 AND score_awarded <= 5.0", name="score_awarded_range"
        ),
        Index("ix_performance_evaluations_trainer_date", "trainer_id", "evaluation_date"),
        Index("ix_performance_evaluations_programme_id", "programme_id"),
        Index("ix_performance_evaluations_evaluated_by_user_id", "evaluated_by_user_id"),
        {"comment": "Post-course trainer ratings. Read on every prediction run. FR-10."},
    )

    evaluation_id: Mapped[int] = primary_key()
    registry_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        comment="e.g. 'TPS/EVL/2026/0088'. From next_registry_number('EVL').",
    )
    allocation_id: Mapped[int] = mapped_column(
        ForeignKey("allocations.allocation_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="One evaluation per allocation. UNIQUE makes double-rating impossible.",
    )
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="RESTRICT"),
        nullable=False,
        comment="Denormalised from the allocation. See class docstring.",
    )
    programme_id: Mapped[int] = mapped_column(
        ForeignKey("training_programmes.programme_id", ondelete="RESTRICT"),
        nullable=False,
        comment="Denormalised from the allocation. Drives the relevance test.",
    )
    score_awarded: Mapped[Decimal] = mapped_column(
        Rating, nullable=False, comment="1.0 to 5.0, one decimal place. NUMERIC, never float (D4)."
    )
    evaluator_comments: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Required: a bare number is not an evaluation."
    )
    evaluated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="Date of assessment, which may precede the record's creation."
    )

    allocation: Mapped[Allocation] = relationship(lazy="raise_on_sql")
    trainer: Mapped[Trainer] = relationship(lazy="raise_on_sql")
    programme: Mapped[TrainingProgramme] = relationship(lazy="raise_on_sql")
    evaluated_by: Mapped[User] = relationship(lazy="raise_on_sql")
