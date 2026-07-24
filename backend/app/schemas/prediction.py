"""Prediction schemas (§6.5).

The shapes here are what the frontend's Score Ledger, Exclusion Ledger, and Weight
Studio render. Field names follow ``frontend/src/types/domain.ts``.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import CamelModel, ScoreField


class CriterionScoreRead(CamelModel):
    """One row of the Score Ledger.

    Every number here is separately readable and sums to the total, which is the whole
    reason the system uses an additive model rather than something more sophisticated.
    """

    key: str
    label: str
    weight: ScoreField
    raw_value: str = Field(description="The underlying evidence, e.g. 'Advanced · Cybercrime'.")
    normalized: ScoreField = Field(description="0-100 before weighting.")
    contribution: ScoreField = Field(description="weight × normalized / 100.")
    explanation: str
    data_quality: str = Field(
        description="COMPLETE, PARTIAL, or MISSING. Drives the amber marker in the UI."
    )


class PredictionRead(CamelModel):
    """One ranked candidate."""

    prediction_id: int | None = Field(
        default=None, description="Null for an unpersisted simulation."
    )
    programme_id: int
    trainer_id: int
    trainer_name: str
    trainer_rank: str
    force_number: str
    station: str
    prediction_score: ScoreField
    confidence_level: int = Field(
        description=(
            "0-100. Measures how much the system **knows about this trainer**, not how "
            "likely they are to succeed. A strong trainer with no evaluation history "
            "scores LOW."
        )
    )
    confidence_band: str
    rank_position: int
    breakdown: list[CriterionScoreRead]
    rationale: str
    counterfactual: str | None = Field(
        default=None,
        description=(
            "The smallest single change that would reach rank 1, for ranks 2-5. Null "
            "when no single change closes the gap — never an approximation."
        ),
    )
    generated_at: datetime.datetime | None = None


class ExclusionRead(CamelModel):
    """One entry in the Exclusion Ledger."""

    trainer_id: int
    full_name: str
    police_rank: str
    force_number: str
    reason: str
    reason_detail: str = Field(description="Officer-readable sentence, rendered verbatim.")
    business_rule: str = Field(description="BR-03, BR-04, or FR-05.")


class ExclusionGroup(CamelModel):
    """Exclusions grouped by reason, as §6.5 requires."""

    reason: str
    business_rule: str
    count: int
    trainers: list[ExclusionRead]


class PredictionRunRead(CamelModel):
    """A complete prediction run.

    **Always ordered by `rankPosition` ascending.** There is no `sortBy` parameter on
    this endpoint: BR-05 fixes the order, and letting a client re-sort a ranked list
    would let the interface present a different recommendation from the one recorded.
    """

    run_id: int | None = Field(default=None, description="Null for a simulation.")
    programme_id: int
    programme_title: str
    generated_at: datetime.datetime
    generated_by_name: str | None = None
    candidate_pool_size: int
    excluded_count: int
    ranked_count: int
    elapsed_ms: int
    weights: dict[str, float]
    weights_are_policy_default: bool = True
    is_superseded: bool = False
    prior_mean: ScoreField | None = Field(
        default=None,
        description=(
            "The shrinkage prior in force for this run — the mean of every evaluation "
            "in the system at the time. Stored so an old run reproduces exactly."
        ),
    )
    predictions: list[PredictionRead] = Field(default_factory=list)
    excluded: list[ExclusionRead] = Field(default_factory=list)


class RankDelta(CamelModel):
    """How one trainer's rank moved under simulated weights."""

    trainer_id: int
    trainer_name: str
    previous_rank: int | None = None
    new_rank: int | None = None
    movement: int = Field(description="Positive means improved. Null ranks mean newly in or out.")


class SimulationRequest(CamelModel):
    """A Weight Studio simulation (§6.5).

    Runs the identical engine with override weights and **persists nothing** except a
    `WEIGHTS_SIMULATED` audit entry. Same code path as a real run — duplicating the
    engine for preview is how a preview silently diverges from reality.
    """

    programme_id: int = Field(gt=0)
    weights: dict[str, Decimal] = Field(
        description="Criterion key to weight. Must total 100.",
        examples=[
            {
                "SPECIALIZATION": 45,
                "PERFORMANCE": 20,
                "EXPERIENCE": 15,
                "QUALIFICATION": 15,
                "AVAILABILITY": 5,
            }
        ],
    )


class SimulationResponse(CamelModel):
    """A simulation result, with the movement against the persisted run."""

    run: PredictionRunRead
    rank_deltas: list[RankDelta] = Field(default_factory=list)
    persisted: bool = Field(default=False, description="Always false — simulations are not saved.")
