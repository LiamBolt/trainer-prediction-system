"""The prediction engine — orchestration of all four stages (§5).

**Pure and side-effect free.** No database session, no HTTP, no clock reading, no I/O
of any kind. Everything it needs arrives as arguments, which is what makes it
exhaustively unit-testable and what lets the Weight Studio's in-memory simulation reuse
it unchanged (§5.8). Duplicating the engine for simulation is precisely how a preview
silently diverges from reality.

The pipeline:

1. **Gate** — eliminate on BR-03, BR-04, FR-05. Excluded trainers are recorded, not
   ranked.
2. **Score** — normalise five criteria, weight them, sum.
3. **Rank** — sort descending with a deterministic lexicographic tie-break.
4. **Narrate** — a rationale for every candidate, a counterfactual for ranks 2-5.

This is **weighted multi-criteria decision analysis**, not machine learning. There is
no trained model, no probability, and nothing here predicts the future. It scores
present evidence against stated requirements in a way a human can check by hand. See
``docs/ALGORITHMS.md`` for why that was the right choice and what was rejected.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from decimal import Decimal

from app.models.enums import CriterionKey
from app.services.prediction.confidence import compute_confidence
from app.services.prediction.criteria import (
    CRITERIA,
    CRITERION_ORDER,
    DEFAULT_PRIOR_MEAN,
    quantise,
    shrunk_mean,
)
from app.services.prediction.gates import evaluate_gates
from app.services.prediction.narrative import (
    COUNTERFACTUAL_MAX_RANK,
    COUNTERFACTUAL_MIN_RANK,
    build_counterfactual,
    build_rationale,
)
from app.services.prediction.types import (
    CandidateFacts,
    CriterionScore,
    EligibilityPreview,
    Exclusion,
    PredictionRunResult,
    ProgrammeRequirements,
    ScoredCandidate,
)

HUNDRED = Decimal("100")

#: Weights must total this. Enforced here as well as in the database's deferred
#: trigger, because a simulation never touches the database and would otherwise be
#: able to produce a score on a scale nobody else uses.
REQUIRED_WEIGHT_TOTAL = Decimal("100")


class WeightsError(ValueError):
    """Raised when a weight set is unusable.

    A plain ``ValueError`` subclass rather than a domain exception: this signals a
    programming or input error at the engine boundary, and the service layer converts
    it into a 422 for the caller. Keeping it framework-free preserves B7.
    """


def validate_weights(weights: dict[CriterionKey, Decimal]) -> None:
    """Check a weight set before it is used.

    Args:
        weights: Criterion weights.

    Raises:
        WeightsError: If a key is unknown, a weight is negative, or the total is not
            exactly 100.
    """
    unknown = set(weights) - set(CRITERIA)
    if unknown:
        names = ", ".join(sorted(key.value for key in unknown))
        raise WeightsError(f"Unknown scoring criteria: {names}.")

    negative = [key.value for key, value in weights.items() if value < 0]
    if negative:
        raise WeightsError(f"Weights cannot be negative: {', '.join(sorted(negative))}.")

    total = sum(weights.values(), start=Decimal("0"))
    if total != REQUIRED_WEIGHT_TOTAL:
        raise WeightsError(f"Weights must total 100, but they total {total}.")


def score_candidate(
    facts: CandidateFacts,
    programme: ProgrammeRequirements,
    weights: dict[CriterionKey, Decimal],
    *,
    today: datetime.date,
    prior_mean: Decimal,
) -> ScoredCandidate:
    """Score one candidate across every criterion.

    Args:
        facts: The candidate.
        programme: The requirements.
        weights: Criterion weights.
        today: Reference date for the confidence recency decay.
        prior_mean: The shrinkage prior for this run.

    Returns:
        The scored candidate, without a rank or narrative yet.
    """
    breakdown: list[CriterionScore] = []
    for key in CRITERION_ORDER:
        criterion = CRITERIA[key]
        weight = weights.get(key, Decimal("0"))
        normalized, raw_value, explanation, quality = criterion.score(facts, programme, prior_mean)
        breakdown.append(
            CriterionScore(
                key=key,
                label=criterion.label,
                weight=weight,
                raw_value=raw_value,
                normalized=normalized,
                contribution=quantise(weight * normalized / HUNDRED),
                explanation=explanation,
                data_quality=quality,
            )
        )

    total = quantise(sum((item.contribution for item in breakdown), start=Decimal("0")))
    level, band = compute_confidence(facts, today)

    # The same shrunk mean the PERFORMANCE criterion used, recomputed through the
    # shared helper so the tie-break can never disagree with the score.
    use_area = facts.evaluation_count_in_area >= 2 and facts.evaluation_mean_in_area is not None
    performance_mean = shrunk_mean(
        facts.evaluation_count_in_area if use_area else facts.evaluation_count,
        facts.evaluation_mean_in_area if use_area else facts.evaluation_mean,
        prior_mean,
    )

    return ScoredCandidate(
        facts=facts,
        breakdown=tuple(breakdown),
        total=total,
        performance_mean=performance_mean,
        confidence_level=level,
        confidence_band=band,
    )


def _sort_key(candidate: ScoredCandidate) -> tuple[Decimal, Decimal, int, int, int]:
    """Deterministic ranking key (§5.6, BR-05).

    Lexicographic order: total score, then shrunk performance mean, then years of
    service, then *fewer* active allocations, then lower force number.

    The final term guarantees a **total order**. That is not fussiness: if two runs
    over unchanged data could produce different orderings, the audit trail would be
    worthless — an officer could not demonstrate that the ranking they acted on is the
    ranking the system produces. Force number is arbitrary but stable, which is exactly
    what a final tie-break needs to be.

    Negated fields sort descending under Python's ascending default.
    """
    return (
        -candidate.total,
        -candidate.performance_mean,
        -candidate.facts.years_experience,
        candidate.facts.active_allocation_count,
        int(candidate.facts.force_number) if candidate.facts.force_number.isdigit() else 0,
    )


def generate_prediction(
    programme: ProgrammeRequirements,
    candidates: Sequence[CandidateFacts],
    weights: dict[CriterionKey, Decimal],
    *,
    today: datetime.date,
    prior_mean: Decimal = DEFAULT_PRIOR_MEAN,
    elapsed_ms: int = 0,
) -> PredictionRunResult:
    """Score, rank, and explain every eligible trainer for a programme.

    Runs the four-stage pipeline documented in ``docs/ALGORITHMS.md`` §3: hard gates
    (BR-03, BR-04, FR-05), weighted criterion scoring, ranking with a deterministic
    tie-break (BR-05), and narrative generation.

    The function is pure. It performs no I/O and takes no database session, so it is
    exhaustively unit-testable and is reused unchanged for the Weight Studio's
    in-memory simulation (§5.8).

    Args:
        programme: The programme being staffed. Its required specialisation must be
            set; callers enforce that per FR-05 before reaching here.
        candidates: **Every** trainer in the pool, pre-projected by the repository —
            including those who will be gated out. Exclusion is decided here, not by
            the caller, so the Exclusion Ledger can report on the whole pool.
        weights: Criterion weights totalling 100, from the active scoring policy or
            overridden for simulation.
        today: Injected date. Never read the clock inside this module; the recency
            component of confidence depends on it and must be testable.
        prior_mean: Shrinkage prior, the mean of every evaluation in the system.
        elapsed_ms: Measured duration, supplied by the caller that timed the whole
            operation including I/O (NFR-01).

    Returns:
        Ranked predictions, exclusions with reasons, the weights used, and timing.

    Raises:
        WeightsError: If ``weights`` is invalid.

    Example:
        >>> result = generate_prediction(programme, facts, weights, today=date.today())
        >>> result.predictions[0].rank_position
        1
    """
    validate_weights(weights)

    exclusions: list[Exclusion] = []
    scored: list[ScoredCandidate] = []

    for facts in candidates:
        exclusion = evaluate_gates(facts, programme)
        if exclusion is not None:
            exclusions.append(exclusion)
            continue
        scored.append(
            score_candidate(facts, programme, weights, today=today, prior_mean=prior_mean)
        )

    scored.sort(key=_sort_key)

    top_total = scored[0].total if scored else Decimal("0")
    ranked: list[ScoredCandidate] = []
    for index, candidate in enumerate(scored, start=1):
        rationale = build_rationale(candidate.facts, programme, candidate.breakdown)
        counterfactual = (
            build_counterfactual(candidate, top_total, weights, prior_mean, programme)
            if COUNTERFACTUAL_MIN_RANK <= index <= COUNTERFACTUAL_MAX_RANK
            else None
        )
        # Frozen dataclass: rebuild rather than mutate, so a scored candidate can
        # never be altered after the fact.
        ranked.append(
            ScoredCandidate(
                facts=candidate.facts,
                breakdown=candidate.breakdown,
                total=candidate.total,
                performance_mean=candidate.performance_mean,
                confidence_level=candidate.confidence_level,
                confidence_band=candidate.confidence_band,
                rank_position=index,
                rationale=rationale,
                counterfactual=counterfactual,
            )
        )

    return PredictionRunResult(
        programme_id=programme.programme_id,
        predictions=tuple(ranked),
        exclusions=tuple(exclusions),
        weights=dict(weights),
        candidate_pool_size=len(candidates),
        elapsed_ms=elapsed_ms,
        prior_mean=prior_mean,
    )


def preview_eligibility(
    programme: ProgrammeRequirements, candidates: Sequence[CandidateFacts]
) -> EligibilityPreview:
    """Run the gates only, returning counts (§6.4).

    Powers the live preview on the requirements form: *"142 of 812 trainers meet these
    criteria."* Its value is that an officer discovers criteria that are too narrow
    **before** spending a prediction run, rather than after staring at a list of three.

    Deliberately cheap — gates only, no scoring, no narrative.

    Args:
        programme: The requirements being previewed.
        candidates: The full pool.

    Returns:
        Eligible and total counts, plus a breakdown by exclusion reason.
    """
    by_reason: dict[str, int] = {}
    eligible = 0
    for facts in candidates:
        exclusion = evaluate_gates(facts, programme)
        if exclusion is None:
            eligible += 1
        else:
            key = exclusion.reason.value
            by_reason[key] = by_reason.get(key, 0) + 1
    return EligibilityPreview(eligible=eligible, total=len(candidates), by_reason=by_reason)
