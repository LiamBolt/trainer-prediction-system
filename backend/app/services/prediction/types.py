"""Frozen value types for the prediction engine.

Everything here is immutable. The engine is a pure function from facts to a result,
and immutability is what makes that claim checkable: nothing downstream can mutate a
candidate's score after the fact and leave the audit trail describing something that
never happened.

**No arithmetic in this package uses `float`** (B10). The single exception is
:meth:`CriterionScore.to_json`, which converts to `float` at the JSONB/JSON boundary
because JSON has no decimal type — by which point the value has already been quantised
to two places while still exact. Nothing is ever computed from those floats; the
authoritative value is the `NUMERIC` column beside them.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from app.models.enums import (
    BusinessRule,
    ConfidenceBand,
    CriterionKey,
    DataQuality,
    ExclusionReason,
)


@dataclass(frozen=True, slots=True)
class ScheduleConflict:
    """An existing commitment overlapping the programme's dates.

    Attributes:
        title: What the trainer is already committed to. Rendered verbatim in the
            Exclusion Ledger, so it must read as a course or a reason, not an id.
        start_date: First day of the clash.
        end_date: Last day of the clash.
        kind: ``"ALLOCATION"`` or ``"UNAVAILABILITY"``.
    """

    title: str
    start_date: datetime.date
    end_date: datetime.date
    kind: str


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    """Everything the engine knows about one trainer, projected in a single query.

    Deliberately flat and primitive. The engine never holds an ORM entity, never
    triggers a lazy load, and never reaches back to the database — which is what lets
    the whole of §5 be unit-tested without one, and what makes the Weight Studio's
    in-memory simulation use the identical code path (§5.8).

    Attributes:
        trainer_id: Primary key.
        full_name: For the narrative sentence.
        rank_code: e.g. ``"ASP"``. Used in the rationale.
        force_number: Also the final, arbitrary-but-stable tie-break.
        station_name: Posting.
        years_experience: Years of service.
        availability_status: ``AVAILABLE``, ``ASSIGNED``, or ``UNAVAILABLE``.
        highest_qualification_score: Score of the trainer's best qualification, from
            ``qualification_levels``. None when nothing is recorded.
        highest_qualification_order: Its rank order, for the FR-05 minimum gate.
        highest_qualification_name: Its display name, for the narrative.
        has_police_institution_qualification: Whether any qualification came from a
            police training institution.
        proficiency_score_in_required_area: Score of the trainer's proficiency in the
            programme's required discipline. **None means they do not hold it**, which
            is the BR-04 gate.
        proficiency_name_in_required_area: e.g. ``"Advanced"``.
        has_group_matching_specialisation: Whether a *second* specialisation shares
            the programme's discipline group, earning the breadth bonus.
        evaluation_count: Total evaluations recorded.
        evaluation_mean: Mean rating across all of them, or None.
        evaluation_count_in_area: Evaluations within the programme's discipline group.
        evaluation_mean_in_area: Mean within that group, or None.
        last_evaluation_date: Most recent evaluation, for the recency decay.
        active_allocation_count: Allocations currently occupying the trainer.
        last_assigned_date: Most recent approval, for the utilisation report.
        profile_completeness: 0-100, contributing 35% of confidence.
        conflict: An overlapping commitment, or None.
    """

    trainer_id: int
    full_name: str
    rank_code: str
    force_number: str
    station_name: str
    years_experience: int
    availability_status: str

    highest_qualification_score: Decimal | None = None
    highest_qualification_order: int | None = None
    highest_qualification_name: str | None = None
    has_police_institution_qualification: bool = False

    proficiency_score_in_required_area: Decimal | None = None
    proficiency_name_in_required_area: str | None = None
    has_group_matching_specialisation: bool = False

    evaluation_count: int = 0
    evaluation_mean: Decimal | None = None
    evaluation_count_in_area: int = 0
    evaluation_mean_in_area: Decimal | None = None
    last_evaluation_date: datetime.date | None = None

    active_allocation_count: int = 0
    last_assigned_date: datetime.date | None = None
    profile_completeness: int = 0

    conflict: ScheduleConflict | None = None


@dataclass(frozen=True, slots=True)
class ProgrammeRequirements:
    """The requirements a candidate is scored against.

    Attributes:
        programme_id: Primary key.
        title: Course title, for conflict messages.
        required_specialization_area_id: The discipline BR-04 matches on. Never None
            by the time the engine runs — callers enforce FR-05 first.
        required_specialization_name: Its display name, for narrative and exclusions.
        discipline_group: Subject grouping, driving the breadth bonus and the
            evaluation relevance test (ADR-0008). May be None.
        minimum_experience: FR-05 minimum years.
        minimum_qualification_order: FR-05 minimum qualification rank, or None.
        minimum_qualification_name: Its display name, for the exclusion message.
        start_date: Course start.
        end_date: Course end.
    """

    programme_id: int
    title: str
    required_specialization_area_id: int
    required_specialization_name: str
    discipline_group: str | None
    minimum_experience: int
    minimum_qualification_order: int | None
    minimum_qualification_name: str | None
    start_date: datetime.date
    end_date: datetime.date


@dataclass(frozen=True, slots=True)
class CriterionScore:
    """One criterion's contribution to a candidate's total.

    This is the row the frontend's Score Ledger renders, and the reason the whole
    system uses an additive model: every number here is separately readable and adds
    up to the total in a way a human can check by hand.

    Attributes:
        key: Which criterion.
        label: Human-facing name.
        weight: Points available under the active policy.
        raw_value: The underlying evidence, e.g. ``"Advanced · Cybercrime
            Investigation"``.
        normalized: 0-100, before weighting.
        contribution: ``weight × normalized / 100``.
        explanation: One plain-English sentence.
        data_quality: ``COMPLETE``, ``PARTIAL``, or ``MISSING``. The frontend renders
            an amber marker from this — a substituted default is never silent.
    """

    key: CriterionKey
    label: str
    weight: Decimal
    raw_value: str
    normalized: Decimal
    contribution: Decimal
    explanation: str
    data_quality: DataQuality

    def to_json(self) -> dict[str, object]:
        """Render for JSONB storage and the wire.

        Keys are camelCase because this payload is served to the frontend verbatim
        and stored frozen on the allocation; re-mapping five keys per candidate per
        read would be waste for a value written once and never queried inside.

        Returns:
            A JSON-safe dictionary.
        """
        return {
            "key": self.key.value,
            "label": self.label,
            "weight": float(self.weight),
            "rawValue": self.raw_value,
            "normalized": float(self.normalized),
            "contribution": float(self.contribution),
            "explanation": self.explanation,
            "dataQuality": self.data_quality.value,
        }


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A trainer removed by a hard gate, with the rule that removed them.

    Attributes:
        trainer_id: Who was excluded.
        full_name: For display in the Exclusion Ledger.
        rank_code: For display.
        force_number: For display.
        reason: Machine-readable reason code.
        reason_detail: **Human-readable** sentence, read by a non-technical officer.
        business_rule: The rule citation, e.g. ``BR-03``.
    """

    trainer_id: int
    full_name: str
    rank_code: str
    force_number: str
    reason: ExclusionReason
    reason_detail: str
    business_rule: BusinessRule


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A trainer who passed every gate, with their score, ranking, and explanation.

    Attributes:
        facts: The inputs this score was computed from.
        breakdown: Per-criterion scores, in display order.
        total: Weighted total, 0-100.
        performance_mean: The shrunk mean used, for the tie-break.
        confidence_level: 0-100 data completeness.
        confidence_band: Its band.
        rank_position: 1-based rank, assigned after sorting.
        rationale: One-sentence justification.
        counterfactual: The smallest single change reaching rank 1, or None.
    """

    facts: CandidateFacts
    breakdown: tuple[CriterionScore, ...]
    total: Decimal
    performance_mean: Decimal
    confidence_level: int
    confidence_band: ConfidenceBand
    rank_position: int = 0
    rationale: str = ""
    counterfactual: str | None = None


@dataclass(frozen=True, slots=True)
class PredictionRunResult:
    """The complete output of one engine run.

    Attributes:
        programme_id: What was staffed.
        predictions: Ranked candidates, best first.
        exclusions: Every gated-out trainer, with reasons.
        weights: The weights used, frozen.
        candidate_pool_size: Trainers considered before any gate.
        elapsed_ms: Wall-clock duration (NFR-01).
        prior_mean: The shrinkage prior in force for this run, recorded so a score can
            be reproduced exactly — the prior moves as the system accumulates
            evaluations, so a run is only reproducible if it is stored.
    """

    programme_id: int
    predictions: tuple[ScoredCandidate, ...]
    exclusions: tuple[Exclusion, ...]
    weights: dict[CriterionKey, Decimal]
    candidate_pool_size: int
    elapsed_ms: int = 0
    prior_mean: Decimal = Decimal("3.2")

    @property
    def ranked_count(self) -> int:
        """How many candidates were scored."""
        return len(self.predictions)

    @property
    def excluded_count(self) -> int:
        """How many candidates were gated out."""
        return len(self.exclusions)


@dataclass(frozen=True, slots=True)
class EligibilityPreview:
    """Gate-only counts, for the live preview on the requirements form (§6.4).

    Cheap by construction: it runs the gates and stops, with no scoring and no
    narrative. Its purpose is to let an officer discover that their criteria are too
    narrow *before* spending a prediction run.

    Attributes:
        eligible: Trainers passing every gate.
        total: The whole pool.
        by_reason: Exclusion counts keyed by reason.
    """

    eligible: int
    total: int
    by_reason: dict[str, int] = field(default_factory=dict)
