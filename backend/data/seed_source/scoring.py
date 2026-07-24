"""A faithful port of the frontend prediction engine, for seed generation only.

**This is not the production scoring engine.** Phase 2 (`03-BACKEND-PROMPT.md`)
implements that in ``app/services/``, reading its weights from
``scoring_policy_weights`` and its score values from the lookup tables. This module
exists because the seed must write ``predictions.prediction_score``,
``predictions.breakdown``, and ``predictions.rationale`` — and those values have to be
*consistent with each other* and with the frontend's Score Ledger, not invented.

It is a line-by-line port of ``frontend/src/lib/scoring/`` (``gates.ts``,
``criteria.ts``, ``score.ts``, ``narrative.ts``), with two deliberate differences:

1. **Decimal, not float** (D4). The frontend rounds binary floats; here every
   intermediate is a :class:`~decimal.Decimal` quantized with ``ROUND_HALF_UP`` so the
   stored ``NUMERIC`` values reproduce byte-for-byte.
2. **Structural lookups.** "Is this a police institution?" is
   ``institution_type == 'POLICE'`` rather than a name-set membership test, and
   "is this evaluation relevant?" compares ``discipline_group`` rather than a
   hard-coded category map (ADR-0008).

Living in ``data/seed_source/`` rather than ``app/`` is the point: Phase 2's engine is
a clean-room implementation against the same specification, and if the two disagree
that disagreement is a finding, not a merge conflict.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.constants import (
    CONFIDENCE_EVALUATION_DEPTH_TARGET,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MODERATE_THRESHOLD,
    EXPERIENCE_CEILING_YEARS,
    PERFORMANCE_COLD_START_SCORE,
    QUALIFICATION_POLICE_INSTITUTION_BONUS,
    RELEVANT_EVALUATION_MINIMUM,
    SPECIALIZATION_BREADTH_BONUS,
)
from app.models.enums import (
    AvailabilityStatus,
    BusinessRule,
    ConfidenceBand,
    CriterionKey,
    DataQuality,
    ExclusionReason,
)

ZERO: Final = Decimal("0")
HUNDRED: Final = Decimal("100")
ONE_DP: Final = Decimal("0.1")
TWO_DP: Final = Decimal("0.01")

#: Which business rule each exclusion reason cites.
BUSINESS_RULE_FOR: Final[dict[str, str]] = {
    ExclusionReason.UNAVAILABLE: BusinessRule.BR_03,
    ExclusionReason.SCHEDULE_CONFLICT: BusinessRule.BR_03,
    ExclusionReason.MISSING_SPECIALIZATION: BusinessRule.BR_04,
    ExclusionReason.BELOW_MINIMUM_EXPERIENCE: BusinessRule.FR_05,
    ExclusionReason.BELOW_MINIMUM_QUALIFICATION: BusinessRule.FR_05,
}

PROFICIENCY_LABEL: Final[dict[str, str]] = {
    "BASIC": "Basic",
    "INTERMEDIATE": "Intermediate",
    "ADVANCED": "Advanced",
    "EXPERT": "Expert",
}

QUALIFICATION_LABEL: Final[dict[str, str]] = {
    "CERTIFICATE": "Certificate",
    "DIPLOMA": "Diploma",
    "BACHELORS": "Bachelor's degree",
    "POSTGRAD_DIPLOMA": "Postgraduate diploma",
    "MASTERS": "Master's degree",
    "DOCTORATE": "Doctorate",
}

CRITERION_LABEL: Final[dict[str, str]] = {
    CriterionKey.SPECIALIZATION: "Specialisation match",
    CriterionKey.PERFORMANCE: "Proven performance",
    CriterionKey.EXPERIENCE: "Years of service",
    CriterionKey.QUALIFICATION: "Qualification",
    CriterionKey.AVAILABILITY: "Availability",
}

#: Display order, heaviest default weight first.
CRITERION_ORDER: Final[tuple[str, ...]] = (
    CriterionKey.SPECIALIZATION,
    CriterionKey.PERFORMANCE,
    CriterionKey.EXPERIENCE,
    CriterionKey.QUALIFICATION,
    CriterionKey.AVAILABILITY,
)

DAYS_PER_MONTH: Final = Decimal("30.4375")


def r1(value: Decimal) -> Decimal:
    """Round to one decimal place, half away from zero."""
    return value.quantize(ONE_DP, rounding=ROUND_HALF_UP)


def r2(value: Decimal) -> Decimal:
    """Round to two decimal places, half away from zero."""
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def clamp(value: Decimal) -> Decimal:
    """Clamp to 0-100 and round to two decimals."""
    return r2(max(ZERO, min(HUNDRED, value)))


# --- Seed-time value objects ----------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedQualification:
    """A qualification, flattened for scoring."""

    level_code: str
    level_order: int
    level_score: Decimal
    institution_name: str
    institution_is_police: bool


@dataclass(frozen=True, slots=True)
class SeedSpecialization:
    """A specialisation, flattened for scoring."""

    area_name: str
    discipline_group: str | None
    proficiency_code: str
    proficiency_score: Decimal


@dataclass(frozen=True, slots=True)
class SeedEvaluation:
    """A past evaluation, flattened for scoring."""

    programme_id: int
    discipline_group: str | None
    score_awarded: Decimal
    evaluation_date: datetime.date


@dataclass(slots=True)
class SeedTrainer:
    """Everything the engine needs to know about one trainer."""

    trainer_id: int
    full_name: str
    rank_code: str
    force_number: str
    years_experience: int
    availability_status: str
    current_allocations: int
    profile_completeness: int
    qualifications: list[SeedQualification] = field(default_factory=list)
    specializations: list[SeedSpecialization] = field(default_factory=list)
    evaluations: list[SeedEvaluation] = field(default_factory=list)

    def highest_qualification(self) -> SeedQualification | None:
        """Return the highest qualification by canonical ordering, or None."""
        if not self.qualifications:
            return None
        return max(self.qualifications, key=lambda q: q.level_order)

    def specialization_in(self, area_name: str) -> SeedSpecialization | None:
        """Return the trainer's proficiency in an area, or None."""
        for spec in self.specializations:
            if spec.area_name == area_name:
                return spec
        return None


@dataclass(frozen=True, slots=True)
class SeedProgramme:
    """Everything the engine needs to know about one programme."""

    programme_id: int
    title: str
    required_area_name: str
    discipline_group: str | None
    minimum_experience: int
    minimum_qualification_order: int | None
    minimum_qualification_code: str | None
    start_date: datetime.date
    end_date: datetime.date


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A trainer removed by a gate."""

    trainer_id: int
    reason: str
    reason_detail: str
    business_rule: str


@dataclass(slots=True)
class CriterionResult:
    """One criterion's normalised outcome."""

    normalized: Decimal
    raw_value: str
    explanation: str
    data_quality: str


@dataclass(slots=True)
class ScoredCandidate:
    """A trainer that passed every gate, with their score and breakdown."""

    trainer: SeedTrainer
    results: dict[str, CriterionResult]
    breakdown: list[dict[str, object]]
    total: Decimal
    performance_mean: Decimal | None
    performance_count: int
    confidence_level: int
    confidence_band: str


# --- Stage 1: hard gates (BR-03, BR-04, FR-05) -----------------------------


def evaluate_gates(
    trainer: SeedTrainer,
    programme: SeedProgramme,
    conflict: tuple[str, datetime.date, datetime.date] | None = None,
) -> Exclusion | None:
    """Apply the hard gates in order; the first failure is the recorded reason.

    Elimination, not scoring. Excluded trainers never appear in the ranked list
    (BR-03) but remain inspectable in the Exclusion Ledger.

    Args:
        trainer: The candidate.
        programme: The programme being staffed.
        conflict: An overlapping confirmed allocation as
            ``(title, start_date, end_date)``, or None.

    Returns:
        An :class:`Exclusion` describing the first failed gate, or None if the
        trainer passes every gate.
    """
    # 1 — availability (BR-03)
    if trainer.availability_status == AvailabilityStatus.UNAVAILABLE:
        return _exclusion(
            trainer, ExclusionReason.UNAVAILABLE, "Marked unavailable for assignment."
        )

    # 2 — required specialisation (BR-04)
    if trainer.specialization_in(programme.required_area_name) is None:
        return _exclusion(
            trainer,
            ExclusionReason.MISSING_SPECIALIZATION,
            f"Does not hold the required specialisation ({programme.required_area_name}).",
        )

    # 3 — schedule conflict with a confirmed allocation (BR-03)
    if conflict is not None:
        title, start, end = conflict
        return _exclusion(
            trainer,
            ExclusionReason.SCHEDULE_CONFLICT,
            f"Assigned to {title} · {_format_range(start, end)}.",
        )

    # 4 — minimum experience (FR-05)
    if trainer.years_experience < programme.minimum_experience:
        return _exclusion(
            trainer,
            ExclusionReason.BELOW_MINIMUM_EXPERIENCE,
            f"{trainer.years_experience} years of service; {programme.minimum_experience} required.",
        )

    # 5 — minimum qualification, when one is set (FR-05)
    if programme.minimum_qualification_order is not None:
        highest = trainer.highest_qualification()
        held_order = highest.level_order if highest else -1
        if held_order < programme.minimum_qualification_order:
            held = (
                QUALIFICATION_LABEL[highest.level_code].lower()
                if highest
                else "no formal qualification"
            )
            required = QUALIFICATION_LABEL[programme.minimum_qualification_code or ""].lower()
            return _exclusion(
                trainer,
                ExclusionReason.BELOW_MINIMUM_QUALIFICATION,
                f"Highest qualification is {held}; {required} required.",
            )

    return None


def _exclusion(trainer: SeedTrainer, reason: str, detail: str) -> Exclusion:
    """Build an :class:`Exclusion` with the correct business-rule citation."""
    return Exclusion(
        trainer_id=trainer.trainer_id,
        reason=reason,
        reason_detail=detail,
        business_rule=BUSINESS_RULE_FOR[reason],
    )


def _format_range(start: datetime.date, end: datetime.date) -> str:
    """Format a date range as '10-21 Aug 2026'."""
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{end.day} {start:%b %Y}"
    if start.year == end.year:
        return f"{start.day} {start:%b} - {end.day} {end:%b %Y}"
    return f"{start:%d %b %Y} - {end:%d %b %Y}"


# --- Stage 2: criterion scoring -------------------------------------------


def score_specialization(trainer: SeedTrainer, programme: SeedProgramme) -> CriterionResult:
    """Score the SPECIALIZATION criterion.

    Base score is the proficiency level's ``score_value``; a breadth bonus applies
    when a *second* specialisation falls in the same discipline group as the
    programme, which is evidence of adjacent competence.
    """
    match = trainer.specialization_in(programme.required_area_name)
    if match is None:
        # Defensive: BR-04 should have gated this trainer out already.
        return CriterionResult(
            normalized=ZERO,
            raw_value="No matching specialisation",
            explanation=f"Holds no specialisation in {programme.required_area_name}.",
            data_quality=DataQuality.MISSING,
        )

    has_breadth = any(
        spec.area_name != programme.required_area_name
        and spec.discipline_group is not None
        and spec.discipline_group == programme.discipline_group
        for spec in trainer.specializations
    )
    bonus = Decimal(SPECIALIZATION_BREADTH_BONUS) if has_breadth else ZERO
    label = PROFICIENCY_LABEL[match.proficiency_code]
    breadth_note = (
        f" A second specialisation also fits the {programme.discipline_group} group."
        if has_breadth
        else ""
    )
    return CriterionResult(
        normalized=clamp(match.proficiency_score + bonus),
        raw_value=f"{label} · {programme.required_area_name}",
        explanation=(f"Holds {label} proficiency in {programme.required_area_name}.{breadth_note}"),
        data_quality=DataQuality.COMPLETE,
    )


def score_performance(
    trainer: SeedTrainer, programme: SeedProgramme
) -> tuple[CriterionResult, Decimal | None, int]:
    """Score the PERFORMANCE criterion.

    Evaluations from the programme's own discipline group are preferred, but only
    once there are at least :data:`RELEVANT_EVALUATION_MINIMUM` of them — below that
    the sample is too small to be more informative than the full history.

    A trainer with **no** evaluations receives a neutral prior, not a zero. A system
    with no history must not punish the people it happens to know nothing about; that
    would make the cold-start problem self-reinforcing.

    Returns:
        The criterion result, the mean used (or None), and the evaluation count.
    """
    all_evals = trainer.evaluations
    relevant = [
        e
        for e in all_evals
        if e.discipline_group is not None and e.discipline_group == programme.discipline_group
    ]
    used_relevant = len(relevant) >= RELEVANT_EVALUATION_MINIMUM
    used = relevant if used_relevant else all_evals

    if not used:
        return (
            CriterionResult(
                normalized=Decimal(PERFORMANCE_COLD_START_SCORE),
                raw_value="No evaluations recorded",
                explanation=(
                    "No past evaluations exist yet, so a neutral score was used rather than a zero."
                ),
                data_quality=DataQuality.MISSING,
            ),
            None,
            0,
        )

    mean = sum((e.score_awarded for e in used), start=ZERO) / Decimal(len(used))
    normalized = clamp((mean - Decimal(1)) / Decimal(4) * HUNDRED)
    scope = (
        f"{(programme.discipline_group or 'related').lower()} courses"
        if used_relevant
        else "all recorded courses"
    )
    plural = "" if len(used) == 1 else "s"
    return (
        CriterionResult(
            normalized=normalized,
            raw_value=f"{r1(mean)} of 5 · {len(used)} evaluation{plural}",
            explanation=f"Averaged {r1(mean)} out of 5 across {len(used)} {scope}.",
            data_quality=DataQuality.COMPLETE if used_relevant else DataQuality.PARTIAL,
        ),
        mean,
        len(used),
    )


def score_experience(trainer: SeedTrainer) -> CriterionResult:
    """Score the EXPERIENCE criterion, saturating at the twenty-year ceiling."""
    ceiling = Decimal(EXPERIENCE_CEILING_YEARS)
    ratio = min(Decimal(trainer.years_experience) / ceiling, Decimal(1))
    return CriterionResult(
        normalized=clamp(ratio * HUNDRED),
        raw_value=f"{trainer.years_experience} years",
        explanation=(
            f"Has {trainer.years_experience} years of service "
            f"({EXPERIENCE_CEILING_YEARS} years is the ceiling)."
        ),
        data_quality=DataQuality.COMPLETE,
    )


def score_qualification(trainer: SeedTrainer) -> CriterionResult:
    """Score the QUALIFICATION criterion.

    A bonus applies when any qualification came from a police training institution —
    determined by ``institutions.institution_type``, not by matching names.
    """
    highest = trainer.highest_qualification()
    if highest is None:
        return CriterionResult(
            normalized=ZERO,
            raw_value="None recorded",
            explanation="No formal qualification is on record.",
            data_quality=DataQuality.MISSING,
        )
    from_police = any(q.institution_is_police for q in trainer.qualifications)
    bonus = Decimal(QUALIFICATION_POLICE_INSTITUTION_BONUS) if from_police else ZERO
    label = QUALIFICATION_LABEL[highest.level_code]
    note = " from a police training institution" if from_police else ""
    return CriterionResult(
        normalized=clamp(highest.level_score + bonus),
        raw_value=f"{label} · {highest.institution_name}",
        explanation=f"Highest qualification is a {label.lower()}{note}.",
        data_quality=DataQuality.COMPLETE,
    )


def score_availability(trainer: SeedTrainer) -> CriterionResult:
    """Score the AVAILABILITY criterion — spare teaching capacity, not a gate.

    Each current allocation costs 25 points, and an ``ASSIGNED`` trainer is capped at
    50 regardless. This is the criterion that surfaces over-reliance on a few
    individuals, which is the pattern the SRS problem statement describes.
    """
    normalized = clamp(HUNDRED - Decimal(trainer.current_allocations) * Decimal(25))
    if trainer.availability_status == AvailabilityStatus.ASSIGNED:
        normalized = min(normalized, Decimal(50))
    if trainer.current_allocations == 0:
        load = "no current allocations"
    else:
        plural = "" if trainer.current_allocations == 1 else "s"
        load = f"{trainer.current_allocations} current allocation{plural}"
    state = (
        "Assigned" if trainer.availability_status == AvailabilityStatus.ASSIGNED else "Available"
    )
    return CriterionResult(
        normalized=normalized,
        raw_value=f"{state} · {load}",
        explanation=f"Currently has {load}, leaving room to take on this course.",
        data_quality=DataQuality.COMPLETE,
    )


# --- Stage 3: total, confidence, tie-break, rank ---------------------------


def build_breakdown(
    results: dict[str, CriterionResult], weights: dict[str, Decimal]
) -> list[dict[str, object]]:
    """Build the ``CriterionScore[]`` array stored as JSONB.

    Keys are camelCase because this JSON is served to the frontend verbatim — it is
    the one place in the schema where the wire format leaks into storage, and it does
    so deliberately: re-mapping five keys per candidate per read is pure waste when
    the payload is written once and never queried inside.
    """
    breakdown: list[dict[str, object]] = []
    for key in CRITERION_ORDER:
        result = results[key]
        weight = weights[key]
        breakdown.append(
            {
                "key": key,
                "label": CRITERION_LABEL[key],
                "weight": float(weight),
                "rawValue": result.raw_value,
                "normalized": float(r2(result.normalized)),
                "contribution": float(r1(weight * result.normalized / HUNDRED)),
                "explanation": result.explanation,
                "dataQuality": result.data_quality,
            }
        )
    return breakdown


def compute_total(breakdown: list[dict[str, object]]) -> Decimal:
    """Sum the weighted contributions into a 0-100 total."""
    total = sum((Decimal(str(c["contribution"])) for c in breakdown), start=ZERO)
    return r1(total)


def compute_confidence(trainer: SeedTrainer, now: datetime.date) -> tuple[int, str]:
    """Compute the confidence level and band.

    Confidence measures **data completeness**, not statistical confidence. It blends
    how many evaluations exist (45%), how complete the profile is (35%), and how
    recent the most recent evaluation is (20%). A trainer with no evaluations lands
    in ``LOW`` — which is the honest caveat the SRS requires, not a penalty.

    Args:
        trainer: The candidate.
        now: Reference date for recency.

    Returns:
        The 0-100 level and its band.
    """
    evals = trainer.evaluations
    depth = (
        min(Decimal(len(evals)) / Decimal(CONFIDENCE_EVALUATION_DEPTH_TARGET), Decimal(1)) * HUNDRED
    )

    recency = Decimal(40)
    if evals:
        most_recent = max(e.evaluation_date for e in evals)
        age_months = max(ZERO, Decimal((now - most_recent).days) / DAYS_PER_MONTH)
        if age_months <= 24:
            recency = HUNDRED
        else:
            decayed = HUNDRED - ((age_months - Decimal(24)) / Decimal(36)) * Decimal(60)
            recency = max(Decimal(40), decayed)

    level_dec = (
        Decimal("0.45") * depth
        + Decimal("0.35") * Decimal(trainer.profile_completeness)
        + Decimal("0.20") * recency
    )
    level = int(level_dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if level >= CONFIDENCE_HIGH_THRESHOLD:
        band = ConfidenceBand.HIGH
    elif level >= CONFIDENCE_MODERATE_THRESHOLD:
        band = ConfidenceBand.MODERATE
    else:
        band = ConfidenceBand.LOW
    return level, band


def score_candidate(
    trainer: SeedTrainer,
    programme: SeedProgramme,
    weights: dict[str, Decimal],
    now: datetime.date,
) -> ScoredCandidate:
    """Run every criterion for one trainer and assemble the scored candidate."""
    performance, mean, count = score_performance(trainer, programme)
    results: dict[str, CriterionResult] = {
        CriterionKey.SPECIALIZATION: score_specialization(trainer, programme),
        CriterionKey.PERFORMANCE: performance,
        CriterionKey.EXPERIENCE: score_experience(trainer),
        CriterionKey.QUALIFICATION: score_qualification(trainer),
        CriterionKey.AVAILABILITY: score_availability(trainer),
    }
    breakdown = build_breakdown(results, weights)
    level, band = compute_confidence(trainer, now)
    return ScoredCandidate(
        trainer=trainer,
        results=results,
        breakdown=breakdown,
        total=compute_total(breakdown),
        performance_mean=mean,
        performance_count=count,
        confidence_level=level,
        confidence_band=band,
    )


def sort_key(candidate: ScoredCandidate) -> tuple[Decimal, Decimal, int, int, int]:
    """Deterministic ranking key — BR-05, plus a total tie-break.

    Order: total score descending, then performance mean descending, years of service
    descending, current allocations *ascending* (spread the load), and finally force
    number ascending. The last term guarantees a total order, so two runs over
    identical data cannot produce different rankings. Without it, ranks would jitter
    between runs and the audit trail would be worthless.

    Negated fields sort descending under Python's ascending default.
    """
    return (
        -candidate.total,
        -(candidate.performance_mean if candidate.performance_mean is not None else Decimal(-1)),
        -candidate.trainer.years_experience,
        candidate.trainer.current_allocations,
        int(candidate.trainer.force_number),
    )


# --- Stage 4: narrative ----------------------------------------------------


def _surname(full_name: str) -> str:
    """Return the last word of a name."""
    parts = full_name.split()
    return parts[-1] if parts else full_name


def build_rationale(candidate: ScoredCandidate, programme: SeedProgramme) -> str:
    """Write the one-sentence justification shown beside the rank.

    The most important text in the product: it is what an Administrator reads before
    approving, and what an officer reads when asking why someone was chosen. It cites
    only evidence that exists, and says so plainly when evidence is missing.
    """
    trainer = candidate.trainer
    name = f"{trainer.rank_code} {_surname(trainer.full_name)}"
    match = trainer.specialization_in(programme.required_area_name)
    proficiency = PROFICIENCY_LABEL[match.proficiency_code] if match else "some"
    spec = programme.required_area_name
    years = trainer.years_experience

    if candidate.performance_mean is None:
        return (
            f"{name} holds {proficiency} proficiency in {spec} and has {years} years of "
            "service, but has no recorded evaluations yet — so this ranking rests on "
            "qualifications and availability."
        )

    plural = "" if candidate.performance_count == 1 else "s"
    return (
        f"{name} holds {proficiency} proficiency in {spec}, has {years} years of service, "
        f"and averaged {r1(candidate.performance_mean)} out of 5 across "
        f"{candidate.performance_count} previous {spec.lower()} course{plural}."
    )


def build_counterfactual(
    candidate: ScoredCandidate, top_total: Decimal, weights: dict[str, Decimal]
) -> str | None:
    """Describe the smallest single change that would lift this candidate to rank 1.

    Returned only for ranks 2-5, and only when one change genuinely closes the gap.
    Never invented: if no single lever suffices, the answer is None and the UI shows
    nothing. A counterfactual that cannot actually be acted on is worse than silence,
    because it implies a promise the system cannot keep.

    Returns:
        A sentence, or None when no single change would suffice.
    """
    needed = r1(top_total - candidate.total) + Decimal("0.05")
    if needed <= 0:
        return None  # Already at or above the top score; lost on tie-break alone.

    # Lever 1 — one further evaluation.
    weight_perf = weights[CriterionKey.PERFORMANCE]
    if weight_perf > 0:
        old_norm = candidate.results[CriterionKey.PERFORMANCE].normalized
        required_norm = old_norm + (needed * HUNDRED) / weight_perf
        if required_norm <= HUNDRED:
            required_mean = (required_norm / HUNDRED) * Decimal(4) + Decimal(1)
            count = candidate.performance_count if candidate.performance_mean is not None else 0
            total = (
                candidate.performance_mean * Decimal(count)
                if candidate.performance_mean is not None
                else ZERO
            )
            needed_score = required_mean * Decimal(count + 1) - total
            if needed_score <= 1:
                return "Would rank 1st with one further recorded evaluation."
            if needed_score <= 5:
                rounded = needed_score.quantize(ONE_DP, rounding="ROUND_CEILING")
                return f"Would rank 1st with one further evaluation at {rounded} or above."

    # Lever 2 — additional years of service, below the ceiling.
    weight_exp = weights[CriterionKey.EXPERIENCE]
    if weight_exp > 0 and candidate.trainer.years_experience < EXPERIENCE_CEILING_YEARS:
        old_norm = candidate.results[CriterionKey.EXPERIENCE].normalized
        for extra in range(1, EXPERIENCE_CEILING_YEARS - candidate.trainer.years_experience + 1):
            new_years = candidate.trainer.years_experience + extra
            new_norm = (
                min(Decimal(new_years) / Decimal(EXPERIENCE_CEILING_YEARS), Decimal(1)) * HUNDRED
            )
            delta = weight_exp * (new_norm - old_norm) / HUNDRED
            if delta >= needed:
                plural = "" if extra == 1 else "s"
                return f"Would rank 1st with {extra} more year{plural} of service."

    return None


# --- The run ---------------------------------------------------------------


@dataclass(slots=True)
class RunResult:
    """The complete output of one prediction run."""

    ranked: list[ScoredCandidate]
    excluded: list[Exclusion]
    candidate_pool_size: int


def run_prediction(
    trainers: list[SeedTrainer],
    programme: SeedProgramme,
    weights: dict[str, Decimal],
    now: datetime.date,
    conflicts: dict[int, tuple[str, datetime.date, datetime.date]] | None = None,
) -> RunResult:
    """Execute all four stages against a candidate pool.

    Args:
        trainers: The full candidate pool.
        programme: The programme being staffed.
        weights: Criterion weights, summing to 100.
        now: Reference date for recency calculations.
        conflicts: Per-trainer overlapping confirmed allocations.

    Returns:
        The ranked candidates and the exclusion ledger for this run.
    """
    conflicts = conflicts or {}
    ranked: list[ScoredCandidate] = []
    excluded: list[Exclusion] = []

    for trainer in trainers:
        gate = evaluate_gates(trainer, programme, conflicts.get(trainer.trainer_id))
        if gate is not None:
            excluded.append(gate)
            continue
        ranked.append(score_candidate(trainer, programme, weights, now))

    ranked.sort(key=sort_key)
    return RunResult(ranked=ranked, excluded=excluded, candidate_pool_size=len(trainers))
