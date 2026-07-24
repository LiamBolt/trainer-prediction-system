"""Allocation DTOs — the Decision Receipt (§6.7).

An allocation is the only record in this system that a court could be asked to read.
Everything here is shaped by that: the response carries the score **as it stood at
approval**, the weights that produced it, the rationale the trainer was shown, and the
officer accountable — not a re-derivation from today's data.
"""

from __future__ import annotations

import datetime

from pydantic import Field

from app.schemas.base import CamelModel, ScoreField
from app.schemas.prediction import CriterionScoreRead


class AllocationRead(CamelModel):
    """One approved assignment, frozen at the moment of approval (FR-08, BR-07).

    ``frozenScore``, ``frozenBreakdown``, ``frozenRankPosition``, ``frozenWeights`` and
    ``frozenRationale`` are read from the allocation row, never recomputed. An
    evaluation recorded next month changes tomorrow's rankings; it must not change the
    justification for a decision taken today.
    """

    allocation_id: int
    prediction_id: int
    programme_id: int
    trainer_id: int
    registry_number: str = Field(description="e.g. 'TPS/ALL/2026/0417'.")
    approved_by: int
    approved_by_name: str
    approved_by_rank: str = Field(
        default="", description="The approving officer's rank code, for the receipt's signature line."
    )
    status: str
    approval_date: datetime.datetime
    remarks: str = Field(default="", description="Empty string when the approver gave no note.")

    frozen_score: ScoreField
    frozen_breakdown: list[CriterionScoreRead]
    frozen_rank_position: int
    frozen_weights: dict[str, float]
    frozen_rationale: str = Field(
        description="The rationale as it stood at approval — the text shown to the trainer."
    )
    weights_were_simulated: bool = Field(
        description=(
            "True when the ranking behind this decision was produced with weights other "
            "than the active policy. Derived from the run, never from the request body."
        )
    )

    decline_reason: str | None = None
    declined_at: datetime.datetime | None = None
    responded_at: datetime.datetime | None = None
    superseded_by_allocation_id: int | None = Field(
        default=None,
        description="Set when a decline promoted the next candidate, linking the chain.",
    )


class AllocationListItem(AllocationRead):
    """An allocation with the programme and trainer particulars a list needs."""

    programme_title: str
    programme_registry_number: str = ""
    programme_start_date: datetime.date
    programme_end_date: datetime.date
    programme_location: str
    trainer_name: str
    trainer_rank: str
    trainer_force_number: str
    trainer_station: str
    evaluation_id: int | None = Field(
        default=None, description="Set once FR-10 has recorded a score against this allocation."
    )


class ApproveAllocationInput(CamelModel):
    """The approval request (FR-08, BR-02, BR-06).

    ``programmeId`` and ``trainerId`` are **optional consistency checks**, not inputs:
    both are derived from the prediction. When supplied they must agree with it, which
    catches a stale screen approving a candidate the operator is no longer looking at.

    ``weights`` and ``weightsWereSimulated`` are accepted for compatibility with the
    existing frontend body and then **ignored**. The frozen weights always come from
    the prediction run itself. A receipt whose weights were supplied by the client
    could be made to say anything, which would defeat the purpose of freezing them.
    """

    prediction_id: int = Field(gt=0)
    programme_id: int | None = Field(default=None, gt=0)
    trainer_id: int | None = Field(default=None, gt=0)
    remarks: str = Field(default="", max_length=2000)
    weights: dict[str, float] | None = Field(
        default=None, deprecated=True, description="Ignored. Frozen weights come from the run."
    )
    weights_were_simulated: bool | None = Field(
        default=None, deprecated=True, description="Ignored. Derived from the run."
    )


class DeclineInput(CamelModel):
    """A trainer's refusal (FR-09).

    The reason is **required**. The database enforces it too, with a ``CHECK`` that
    refuses any ``DECLINED`` row without one — a form validator is not a rule.
    """

    allocation_id: int | None = Field(
        default=None, gt=0, description="Ignored; the path parameter is authoritative."
    )
    reason: str = Field(
        min_length=10,
        max_length=2000,
        description=(
            "Why the assignment cannot be taken. Shown to the Administrator, who has to "
            "act on it, so ten characters is the floor."
        ),
    )


class WithdrawInput(CamelModel):
    """An Administrator withdrawing an offer before the trainer answers."""

    reason: str = Field(min_length=10, max_length=2000)


class PromoteNextResponse(CamelModel):
    """The result of promoting the next-ranked candidate after a decline (FR-08)."""

    allocation: AllocationListItem
    reused_existing_run: bool = Field(
        default=True,
        description=(
            "Always true. FR-08 requires that a decline does **not** trigger a new "
            "prediction — the next candidate comes from the ranking already on record, "
            "so the sequence of offers stays explainable from one run."
        ),
    )
    run_id: int
    skipped: list[str] = Field(
        default_factory=list,
        description=(
            "Candidates passed over between the decline and this offer, with the reason. "
            "Each one is also audited as CANDIDATE_SKIPPED."
        ),
    )
    message: str


class AssignmentRead(AllocationListItem):
    """A trainer's own view of an assignment (§6.3).

    Inherits the full receipt: a trainer is entitled to see **why** they were selected,
    not merely that they were. ``frozenRationale`` is the sentence the interface shows.
    """


class AssignmentsResponse(CamelModel):
    """A trainer's assignments, split the way the screen presents them."""

    pending: list[AssignmentRead] = Field(
        default_factory=list, description="Awaiting this trainer's answer."
    )
    upcoming: list[AssignmentRead] = Field(
        default_factory=list, description="Accepted and not yet delivered."
    )
    past: list[AssignmentRead] = Field(
        default_factory=list, description="Delivered, evaluated, declined, or withdrawn."
    )
