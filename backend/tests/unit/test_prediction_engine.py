"""Exhaustive unit tests for the prediction engine (§10, priority 1).

Pure tests — no database, no HTTP, no clock. The engine is a function from facts to a
result, which is what makes this level of coverage cheap enough to be worth having.

Covered here, in the order §10 asks for:

- every gate in isolation and in combination, including gate **precedence**
- every criterion at its boundaries
- shrinkage at n = 0, 1, 3, 12
- confidence bands at their edges
- **determinism** — two runs over identical fixtures produce identical output
- **tie-breaks** — exact ties, resolved in the documented order
- **counterfactuals** — arithmetically true, or None
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from app.models.enums import (
    BusinessRule,
    ConfidenceBand,
    CriterionKey,
    DataQuality,
    ExclusionReason,
)
from app.services.prediction import (
    CandidateFacts,
    ProgrammeRequirements,
    ScheduleConflict,
    WeightsError,
    band_for,
    compute_confidence,
    compute_recency,
    evaluate_gates,
    format_date_range,
    generate_prediction,
    preview_eligibility,
    score_candidate,
    shrunk_mean,
    validate_weights,
)
from app.services.prediction.criteria import CRITERIA, DEFAULT_PRIOR_MEAN

TODAY = datetime.date(2026, 7, 22)

STANDARD_WEIGHTS: dict[CriterionKey, Decimal] = {
    CriterionKey.SPECIALIZATION: Decimal("30"),
    CriterionKey.PERFORMANCE: Decimal("25"),
    CriterionKey.EXPERIENCE: Decimal("20"),
    CriterionKey.QUALIFICATION: Decimal("15"),
    CriterionKey.AVAILABILITY: Decimal("10"),
}


def programme(**overrides: object) -> ProgrammeRequirements:
    """Build a programme with sensible defaults."""
    base: dict[str, object] = {
        "programme_id": 1,
        "title": "Basic Cybercrime Investigation Course — Intake 14",
        "required_specialization_area_id": 1,
        "required_specialization_name": "Cybercrime Investigation",
        "discipline_group": "Investigations",
        "minimum_experience": 3,
        "minimum_qualification_order": None,
        "minimum_qualification_name": None,
        "start_date": datetime.date(2026, 8, 15),
        "end_date": datetime.date(2026, 8, 26),
    }
    base.update(overrides)
    return ProgrammeRequirements(**base)  # type: ignore[arg-type]


def candidate(**overrides: object) -> CandidateFacts:
    """Build a fully eligible candidate, overridable per test."""
    base: dict[str, object] = {
        "trainer_id": 1,
        "full_name": "Sarah Mugisha",
        "rank_code": "IP",
        "force_number": "41927",
        "station_name": "Kibuli",
        "years_experience": 13,
        "availability_status": "AVAILABLE",
        "highest_qualification_score": Decimal("90.00"),
        "highest_qualification_order": 5,
        "highest_qualification_name": "Master's Degree",
        "has_police_institution_qualification": True,
        "proficiency_score_in_required_area": Decimal("100.00"),
        "proficiency_name_in_required_area": "Expert",
        "has_group_matching_specialisation": False,
        "evaluation_count": 6,
        "evaluation_mean": Decimal("4.5"),
        "evaluation_count_in_area": 6,
        "evaluation_mean_in_area": Decimal("4.5"),
        "last_evaluation_date": datetime.date(2026, 5, 1),
        "active_allocation_count": 0,
        "last_assigned_date": None,
        "profile_completeness": 95,
        "conflict": None,
    }
    base.update(overrides)
    return CandidateFacts(**base)  # type: ignore[arg-type]


# --- Gates (BR-03, BR-04, FR-05) ------------------------------------------


def test_eligible_candidate_passes_every_gate() -> None:
    """A fully qualified, available trainer is not excluded."""
    assert evaluate_gates(candidate(), programme()) is None


def test_unavailable_is_excluded_under_br03() -> None:
    """BR-03: a trainer marked unavailable never reaches scoring."""
    result = evaluate_gates(candidate(availability_status="UNAVAILABLE"), programme())
    assert result is not None
    assert result.reason is ExclusionReason.UNAVAILABLE
    assert result.business_rule is BusinessRule.BR_03


def test_missing_specialisation_is_excluded_under_br04() -> None:
    """BR-04: a NULL proficiency means the discipline is not held at all."""
    result = evaluate_gates(candidate(proficiency_score_in_required_area=None), programme())
    assert result is not None
    assert result.reason is ExclusionReason.MISSING_SPECIALIZATION
    assert result.business_rule is BusinessRule.BR_04
    assert "Cybercrime Investigation" in result.reason_detail


def test_schedule_conflict_names_the_clashing_course() -> None:
    """The Exclusion Ledger sentence must be readable by a non-technical officer."""
    conflict = ScheduleConflict(
        title="Digital Forensics Level 2",
        start_date=datetime.date(2026, 8, 10),
        end_date=datetime.date(2026, 8, 21),
        kind="ALLOCATION",
    )
    result = evaluate_gates(candidate(conflict=conflict), programme())
    assert result is not None
    assert result.reason is ExclusionReason.SCHEDULE_CONFLICT
    assert result.reason_detail == "Assigned to Digital Forensics Level 2 · 10-21 Aug 2026."


def test_unavailability_window_conflict_reads_differently_from_an_allocation() -> None:
    """A declared absence and a booked course are both conflicts but different facts."""
    conflict = ScheduleConflict(
        title="Court testimony, Jinja",
        start_date=datetime.date(2026, 8, 14),
        end_date=datetime.date(2026, 8, 27),
        kind="UNAVAILABILITY",
    )
    result = evaluate_gates(candidate(conflict=conflict), programme())
    assert result is not None
    assert result.reason_detail.startswith("Unavailable: Court testimony, Jinja")


def test_below_minimum_experience_is_excluded_under_fr05() -> None:
    """FR-05: years of service below the stated minimum."""
    result = evaluate_gates(candidate(years_experience=2), programme(minimum_experience=5))
    assert result is not None
    assert result.reason is ExclusionReason.BELOW_MINIMUM_EXPERIENCE
    assert result.business_rule is BusinessRule.FR_05
    assert "2 years of service; 5 required" in result.reason_detail


def test_below_minimum_qualification_is_excluded_under_fr05() -> None:
    """FR-05: qualification below the stated minimum."""
    result = evaluate_gates(
        candidate(highest_qualification_order=1, highest_qualification_name="Certificate"),
        programme(minimum_qualification_order=3, minimum_qualification_name="Bachelor's Degree"),
    )
    assert result is not None
    assert result.reason is ExclusionReason.BELOW_MINIMUM_QUALIFICATION


def test_no_qualification_at_all_fails_a_minimum_qualification_gate() -> None:
    """A trainer with nothing recorded cannot satisfy a minimum."""
    result = evaluate_gates(
        candidate(highest_qualification_order=None, highest_qualification_name=None),
        programme(minimum_qualification_order=2, minimum_qualification_name="Diploma"),
    )
    assert result is not None
    assert result.reason is ExclusionReason.BELOW_MINIMUM_QUALIFICATION
    assert "no formal qualification" in result.reason_detail


def test_gate_precedence_reports_the_first_failure_not_the_worst() -> None:
    """Order matters: unavailability is reported even when other gates also fail.

    A trainer who is unavailable *and* under-qualified should be reported as
    unavailable — that is the fact that settles it, and the one an officer can act on.
    """
    result = evaluate_gates(
        candidate(
            availability_status="UNAVAILABLE",
            proficiency_score_in_required_area=None,
            years_experience=1,
        ),
        programme(minimum_experience=10),
    )
    assert result is not None
    assert result.reason is ExclusionReason.UNAVAILABLE


def test_missing_specialisation_outranks_an_experience_failure() -> None:
    """BR-04 precedes FR-05 in the gate order."""
    result = evaluate_gates(
        candidate(proficiency_score_in_required_area=None, years_experience=1),
        programme(minimum_experience=10),
    )
    assert result is not None
    assert result.reason is ExclusionReason.MISSING_SPECIALIZATION


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (datetime.date(2026, 8, 10), datetime.date(2026, 8, 21), "10-21 Aug 2026"),
        (datetime.date(2026, 7, 28), datetime.date(2026, 8, 3), "28 Jul - 3 Aug 2026"),
        (datetime.date(2026, 12, 28), datetime.date(2027, 1, 5), "28 Dec 2026 - 05 Jan 2027"),
    ],
)
def test_date_ranges_read_naturally(
    start: datetime.date, end: datetime.date, expected: str
) -> None:
    """Exclusion sentences are read by people, so date ranges must not be ISO dumps."""
    assert format_date_range(start, end) == expected


# --- Criteria boundaries --------------------------------------------------


@pytest.mark.parametrize(
    ("years", "expected"),
    [(0, "0.00"), (1, "5.00"), (10, "50.00"), (20, "100.00"), (25, "100.00"), (50, "100.00")],
)
def test_experience_saturates_at_twenty_years(years: int, expected: str) -> None:
    """Beyond the ceiling, more service does not increase the score."""
    normalized, _raw, _explanation, _quality = CRITERIA[CriterionKey.EXPERIENCE].score(
        candidate(years_experience=years), programme(), DEFAULT_PRIOR_MEAN
    )
    assert normalized == Decimal(expected)


def test_specialisation_breadth_bonus_applies_and_caps_at_100() -> None:
    """The +10 breadth bonus cannot push a score above 100."""
    without, _r, _e, _q = CRITERIA[CriterionKey.SPECIALIZATION].score(
        candidate(proficiency_score_in_required_area=Decimal("85")), programme(), DEFAULT_PRIOR_MEAN
    )
    with_bonus, _r, _e, _q = CRITERIA[CriterionKey.SPECIALIZATION].score(
        candidate(
            proficiency_score_in_required_area=Decimal("85"),
            has_group_matching_specialisation=True,
        ),
        programme(),
        DEFAULT_PRIOR_MEAN,
    )
    capped, _r, _e, _q = CRITERIA[CriterionKey.SPECIALIZATION].score(
        candidate(has_group_matching_specialisation=True), programme(), DEFAULT_PRIOR_MEAN
    )
    assert without == Decimal("85.00")
    assert with_bonus == Decimal("95.00")
    assert capped == Decimal("100.00")


def test_qualification_police_bonus_applies_and_caps() -> None:
    """The +8 police-college bonus applies and cannot exceed 100."""
    plain, _r, _e, _q = CRITERIA[CriterionKey.QUALIFICATION].score(
        candidate(has_police_institution_qualification=False), programme(), DEFAULT_PRIOR_MEAN
    )
    bonused, _r, _e, _q = CRITERIA[CriterionKey.QUALIFICATION].score(
        candidate(has_police_institution_qualification=True), programme(), DEFAULT_PRIOR_MEAN
    )
    capped, _r, _e, _q = CRITERIA[CriterionKey.QUALIFICATION].score(
        candidate(
            highest_qualification_score=Decimal("100"),
            has_police_institution_qualification=True,
        ),
        programme(),
        DEFAULT_PRIOR_MEAN,
    )
    assert plain == Decimal("90.00")
    assert bonused == Decimal("98.00")
    assert capped == Decimal("100.00")


def test_qualification_absent_is_flagged_missing_not_silently_zeroed() -> None:
    """A substituted value is never silent — the frontend renders an amber marker."""
    normalized, raw, _explanation, quality = CRITERIA[CriterionKey.QUALIFICATION].score(
        candidate(highest_qualification_score=None, highest_qualification_name=None),
        programme(),
        DEFAULT_PRIOR_MEAN,
    )
    assert normalized == Decimal("0")
    assert quality is DataQuality.MISSING
    assert raw == "None recorded"


@pytest.mark.parametrize(
    ("allocations", "status", "expected"),
    [
        (0, "AVAILABLE", "100.00"),
        (1, "AVAILABLE", "75.00"),
        (2, "AVAILABLE", "50.00"),
        (4, "AVAILABLE", "0.00"),
        (9, "AVAILABLE", "0.00"),
        (0, "ASSIGNED", "50.00"),
        (1, "ASSIGNED", "50.00"),
        (3, "ASSIGNED", "25.00"),
    ],
)
def test_availability_penalises_load_and_caps_assigned(
    allocations: int, status: str, expected: str
) -> None:
    """Availability floors at zero and caps ASSIGNED trainers at 50."""
    normalized, _raw, _explanation, _quality = CRITERIA[CriterionKey.AVAILABILITY].score(
        candidate(active_allocation_count=allocations, availability_status=status),
        programme(),
        DEFAULT_PRIOR_MEAN,
    )
    assert normalized == Decimal(expected)


# --- Shrinkage (§5.5) -----------------------------------------------------


def test_shrinkage_with_no_history_returns_exactly_the_prior() -> None:
    """n = 0 must return the prior itself, not an approximation of it."""
    assert shrunk_mean(0, None, DEFAULT_PRIOR_MEAN) == DEFAULT_PRIOR_MEAN


def test_shrinkage_with_no_history_normalises_to_55() -> None:
    """The frontend's flat 55 is a strict special case of the shrinkage formula."""
    normalized, _raw, _explanation, quality = CRITERIA[CriterionKey.PERFORMANCE].score(
        candidate(
            evaluation_count=0,
            evaluation_mean=None,
            evaluation_count_in_area=0,
            evaluation_mean_in_area=None,
        ),
        programme(),
        DEFAULT_PRIOR_MEAN,
    )
    assert normalized == Decimal("55.00")
    assert quality is DataQuality.MISSING


@pytest.mark.parametrize(("count", "expected"), [(1, "25"), (3, "50"), (12, "80")])
def test_shrinkage_moves_toward_evidence_at_the_documented_rate(count: int, expected: str) -> None:
    """With k = 3, weight on own evidence is n/(n+3): 25% at n=1, 80% at n=12."""
    observed = Decimal("5.0")
    result = shrunk_mean(count, observed, DEFAULT_PRIOR_MEAN)
    share = (result - DEFAULT_PRIOR_MEAN) / (observed - DEFAULT_PRIOR_MEAN) * Decimal("100")
    assert share.quantize(Decimal("1")) == Decimal(expected)


def test_shrinkage_is_monotonic_in_evaluation_count() -> None:
    """More evidence moves the estimate steadily toward the observed mean.

    Monotonicity is what stops a newly recorded evaluation from causing a
    discontinuous jump in rank — the property that keeps officers trusting the system.
    """
    observed = Decimal("5.0")
    previous = shrunk_mean(0, None, DEFAULT_PRIOR_MEAN)
    for n in range(1, 30):
        current = shrunk_mean(n, observed, DEFAULT_PRIOR_MEAN)
        assert current > previous
        previous = current


def test_one_lucky_five_does_not_outrank_a_long_strong_record() -> None:
    """The failure mode a raw mean would produce, asserted directly."""
    lucky = shrunk_mean(1, Decimal("5.0"), DEFAULT_PRIOR_MEAN)
    veteran = shrunk_mean(12, Decimal("4.6"), DEFAULT_PRIOR_MEAN)
    assert veteran > lucky


def test_performance_data_quality_reflects_sample_size() -> None:
    """MISSING at n=0, PARTIAL below 3, COMPLETE at 3 and above."""
    for count, expected in (
        (0, DataQuality.MISSING),
        (2, DataQuality.PARTIAL),
        (3, DataQuality.COMPLETE),
    ):
        _n, _raw, _explanation, quality = CRITERIA[CriterionKey.PERFORMANCE].score(
            candidate(
                evaluation_count=count,
                evaluation_mean=Decimal("4.0") if count else None,
                evaluation_count_in_area=0,
                evaluation_mean_in_area=None,
            ),
            programme(),
            DEFAULT_PRIOR_MEAN,
        )
        assert quality is expected


# --- Confidence (§5.6) ----------------------------------------------------


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (0, ConfidenceBand.LOW),
        (44, ConfidenceBand.LOW),
        (45, ConfidenceBand.MODERATE),
        (74, ConfidenceBand.MODERATE),
        (75, ConfidenceBand.HIGH),
        (100, ConfidenceBand.HIGH),
    ],
)
def test_confidence_bands_at_their_exact_edges(level: int, expected: ConfidenceBand) -> None:
    """Band boundaries are inclusive lower bounds."""
    assert band_for(level) is expected


def test_recency_is_full_for_a_fresh_evaluation() -> None:
    """An evaluation recorded today has not decayed."""
    assert compute_recency(TODAY, TODAY) == Decimal("100")


def test_recency_halves_at_the_eighteen_month_half_life() -> None:
    """The decay constant is what the docstring claims it is."""
    eighteen_months_ago = TODAY - datetime.timedelta(days=548)
    value = compute_recency(eighteen_months_ago, TODAY)
    assert Decimal("49") < value < Decimal("51")


def test_recency_floors_at_40_however_old() -> None:
    """Old-but-real evidence is not the same as no evidence."""
    ancient = TODAY - datetime.timedelta(days=365 * 20)
    assert compute_recency(ancient, TODAY) == Decimal("40")


def test_recency_with_no_history_uses_the_floor() -> None:
    """No evaluations scores the same recency as very old ones."""
    assert compute_recency(None, TODAY) == Decimal("40")


def test_zero_evaluation_trainer_lands_in_low_confidence() -> None:
    """The cold-start caveat the SRS requires be visible."""
    level, band = compute_confidence(
        candidate(evaluation_count=0, last_evaluation_date=None, profile_completeness=70),
        TODAY,
    )
    assert level == 33  # 0.45×0 + 0.35×70 + 0.20×40
    assert band is ConfidenceBand.LOW


def test_confidence_measures_data_not_quality() -> None:
    """A poor performer with a full record outranks a strong one with no record.

    This is the distinction the docstrings labour, asserted so it cannot regress.
    """
    poor_but_known, _ = compute_confidence(
        candidate(evaluation_count=8, evaluation_mean=Decimal("2.0"), profile_completeness=100),
        TODAY,
    )
    strong_but_unknown, _ = compute_confidence(
        candidate(
            evaluation_count=0,
            evaluation_mean=None,
            last_evaluation_date=None,
            profile_completeness=60,
        ),
        TODAY,
    )
    assert poor_but_known > strong_but_unknown


# --- Weights validation ---------------------------------------------------


def test_weights_must_total_100() -> None:
    """A simulation never touches the database, so the engine validates too."""
    with pytest.raises(WeightsError, match="must total 100"):
        validate_weights({CriterionKey.SPECIALIZATION: Decimal("30")})


def test_weights_cannot_be_negative() -> None:
    """A negative weight would invert a criterion's meaning."""
    bad = dict(STANDARD_WEIGHTS)
    bad[CriterionKey.AVAILABILITY] = Decimal("-10")
    bad[CriterionKey.SPECIALIZATION] = Decimal("50")
    with pytest.raises(WeightsError, match="negative"):
        validate_weights(bad)


def test_standard_weights_are_valid() -> None:
    """The seeded policy passes its own validator."""
    validate_weights(STANDARD_WEIGHTS)


# --- Ranking, determinism, tie-breaks -------------------------------------


def test_engine_ranks_and_excludes_correctly() -> None:
    """End-to-end: the eligible are ranked, the ineligible are absent."""
    pool = [
        candidate(trainer_id=1, force_number="41001"),
        candidate(trainer_id=2, force_number="41002", availability_status="UNAVAILABLE"),
        candidate(trainer_id=3, force_number="41003", proficiency_score_in_required_area=None),
    ]
    result = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)

    assert result.ranked_count == 1
    assert result.excluded_count == 2
    assert result.predictions[0].rank_position == 1
    # BR-03: excluded trainers are absent from the ranking, not ranked last.
    assert {p.facts.trainer_id for p in result.predictions} == {1}


def test_ranks_are_contiguous_from_one() -> None:
    """rank_position runs 1..n with no gaps — the UNIQUE constraint depends on it."""
    pool = [
        candidate(trainer_id=i, force_number=f"4100{i}", years_experience=i + 3)
        for i in range(1, 9)
    ]
    result = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)
    assert [p.rank_position for p in result.predictions] == list(range(1, 9))


def test_engine_is_deterministic_over_identical_input() -> None:
    """Two runs over unchanged data produce byte-identical rankings.

    If this ever fails, the audit trail is worthless: an officer could not show that
    the ranking they acted on is the ranking the system produces.
    """
    pool = [
        candidate(
            trainer_id=i,
            force_number=f"4{i:04d}",
            years_experience=(i % 18) + 3,
            evaluation_count=i % 7,
            evaluation_mean=Decimal("4.0") if i % 7 else None,
            evaluation_count_in_area=0,
            evaluation_mean_in_area=None,
        )
        for i in range(1, 60)
    ]
    first = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)
    second = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)

    assert [(p.rank_position, p.facts.trainer_id, p.total) for p in first.predictions] == [
        (p.rank_position, p.facts.trainer_id, p.total) for p in second.predictions
    ]
    assert [p.rationale for p in first.predictions] == [p.rationale for p in second.predictions]


def test_tie_break_prefers_higher_performance_mean() -> None:
    """First tie-break: shrunk performance mean, descending."""
    weights = {
        CriterionKey.SPECIALIZATION: Decimal("100"),
        CriterionKey.PERFORMANCE: Decimal("0"),
        CriterionKey.EXPERIENCE: Decimal("0"),
        CriterionKey.QUALIFICATION: Decimal("0"),
        CriterionKey.AVAILABILITY: Decimal("0"),
    }
    weaker = candidate(
        trainer_id=1,
        force_number="41001",
        evaluation_count=5,
        evaluation_mean=Decimal("3.0"),
        evaluation_count_in_area=0,
        evaluation_mean_in_area=None,
    )
    stronger = candidate(
        trainer_id=2,
        force_number="41002",
        evaluation_count=5,
        evaluation_mean=Decimal("4.8"),
        evaluation_count_in_area=0,
        evaluation_mean_in_area=None,
    )
    result = generate_prediction(programme(), [weaker, stronger], weights, today=TODAY)
    assert result.predictions[0].total == result.predictions[1].total
    assert result.predictions[0].facts.trainer_id == 2


def test_tie_break_falls_through_to_force_number() -> None:
    """The final tie-break guarantees a total order over otherwise identical people."""
    a = candidate(trainer_id=1, force_number="49999")
    b = candidate(trainer_id=2, force_number="41111")
    result = generate_prediction(programme(), [a, b], STANDARD_WEIGHTS, today=TODAY)
    assert result.predictions[0].total == result.predictions[1].total
    assert result.predictions[0].facts.force_number == "41111"


def test_tie_break_prefers_the_less_loaded_trainer() -> None:
    """Fewer active allocations wins, spreading work across the pool."""
    weights = {
        CriterionKey.SPECIALIZATION: Decimal("100"),
        CriterionKey.PERFORMANCE: Decimal("0"),
        CriterionKey.EXPERIENCE: Decimal("0"),
        CriterionKey.QUALIFICATION: Decimal("0"),
        CriterionKey.AVAILABILITY: Decimal("0"),
    }
    busy = candidate(trainer_id=1, force_number="41001", active_allocation_count=3)
    free = candidate(trainer_id=2, force_number="41002", active_allocation_count=0)
    result = generate_prediction(programme(), [busy, free], weights, today=TODAY)
    assert result.predictions[0].facts.trainer_id == 2


def test_score_is_the_sum_of_its_contributions() -> None:
    """The Score Ledger must add up — a human checks this by hand."""
    scored = score_candidate(
        candidate(), programme(), STANDARD_WEIGHTS, today=TODAY, prior_mean=DEFAULT_PRIOR_MEAN
    )
    assert sum((c.contribution for c in scored.breakdown), start=Decimal("0")) == scored.total


def test_empty_pool_produces_an_empty_run_not_an_error() -> None:
    """A programme nobody qualifies for is a real outcome, not a failure."""
    result = generate_prediction(programme(), [], STANDARD_WEIGHTS, today=TODAY)
    assert result.ranked_count == 0
    assert result.excluded_count == 0


# --- Counterfactuals (§5.7) -----------------------------------------------


def test_counterfactual_is_arithmetically_true() -> None:
    """A counterfactual must survive being acted on.

    Applies the suggested change and asserts the candidate really would reach the top
    score. A confident, false suggestion is worse than silence.
    """
    leader = candidate(
        trainer_id=1,
        force_number="41001",
        evaluation_count=6,
        evaluation_mean=Decimal("4.8"),
        evaluation_count_in_area=6,
        evaluation_mean_in_area=Decimal("4.8"),
    )
    trailer = candidate(
        trainer_id=2,
        force_number="41002",
        evaluation_count=4,
        evaluation_mean=Decimal("4.0"),
        evaluation_count_in_area=4,
        evaluation_mean_in_area=Decimal("4.0"),
    )
    result = generate_prediction(programme(), [leader, trailer], STANDARD_WEIGHTS, today=TODAY)

    second = result.predictions[1]
    if second.counterfactual is None:
        pytest.skip("No single change closes this gap; None is the correct answer.")

    assert "rank 1st" in second.counterfactual
    if "evaluation at" in second.counterfactual:
        rating = Decimal(second.counterfactual.split("at ")[1].split(" ")[0])
        improved = candidate(
            trainer_id=2,
            force_number="41002",
            evaluation_count=5,
            evaluation_mean=(Decimal("4.0") * 4 + rating) / 5,
            evaluation_count_in_area=5,
            evaluation_mean_in_area=(Decimal("4.0") * 4 + rating) / 5,
        )
        rerun = generate_prediction(programme(), [leader, improved], STANDARD_WEIGHTS, today=TODAY)
        assert rerun.predictions[0].facts.trainer_id == 2


def test_no_counterfactual_for_rank_one() -> None:
    """Rank 1 has nothing to close."""
    pool = [
        candidate(trainer_id=i, force_number=f"4100{i}", years_experience=20 - i)
        for i in range(1, 6)
    ]
    result = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)
    assert result.predictions[0].counterfactual is None


def test_no_counterfactual_beyond_rank_five() -> None:
    """Offering one to rank 40 would be noise dressed as advice."""
    pool = [
        candidate(trainer_id=i, force_number=f"4{i:04d}", years_experience=max(3, 20 - i))
        for i in range(1, 12)
    ]
    result = generate_prediction(programme(), pool, STANDARD_WEIGHTS, today=TODAY)
    for prediction in result.predictions[5:]:
        assert prediction.counterfactual is None


def test_counterfactual_returns_none_when_no_single_change_suffices() -> None:
    """The important negative case — silence rather than an unreachable promise."""
    leader = candidate(trainer_id=1, force_number="41001")
    hopeless = candidate(
        trainer_id=2,
        force_number="41002",
        years_experience=3,
        proficiency_score_in_required_area=Decimal("40"),
        proficiency_name_in_required_area="Basic",
        highest_qualification_score=Decimal("35"),
        highest_qualification_order=1,
        highest_qualification_name="Certificate",
        has_police_institution_qualification=False,
        evaluation_count=0,
        evaluation_mean=None,
        evaluation_count_in_area=0,
        evaluation_mean_in_area=None,
        active_allocation_count=3,
    )
    result = generate_prediction(programme(), [leader, hopeless], STANDARD_WEIGHTS, today=TODAY)
    assert result.predictions[1].counterfactual is None


# --- Rationale ------------------------------------------------------------


def test_rationale_states_the_absence_of_history_plainly() -> None:
    """The honest variant, required by §5.7."""
    result = generate_prediction(
        programme(),
        [
            candidate(
                evaluation_count=0,
                evaluation_mean=None,
                evaluation_count_in_area=0,
                evaluation_mean_in_area=None,
            )
        ],
        STANDARD_WEIGHTS,
        today=TODAY,
    )
    rationale = result.predictions[0].rationale
    assert "no recorded evaluations yet" in rationale
    assert "rests on qualifications and availability" in rationale


def test_rationale_cites_concrete_evidence() -> None:
    """Rank, name, proficiency, service, and the evaluation mean all appear."""
    result = generate_prediction(programme(), [candidate()], STANDARD_WEIGHTS, today=TODAY)
    rationale = result.predictions[0].rationale
    assert "IP Mugisha" in rationale
    assert "Expert proficiency in Cybercrime Investigation" in rationale
    assert "13 years of service" in rationale
    assert "4.5 out of 5" in rationale


def test_rationale_flags_a_provisional_average() -> None:
    """A two-evaluation average is labelled provisional rather than stated flatly."""
    result = generate_prediction(
        programme(),
        [
            candidate(
                evaluation_count=2,
                evaluation_mean=Decimal("4.5"),
                evaluation_count_in_area=0,
                evaluation_mean_in_area=None,
            )
        ],
        STANDARD_WEIGHTS,
        today=TODAY,
    )
    assert "provisional" in result.predictions[0].rationale


# --- Eligibility preview (§6.4) -------------------------------------------


def test_eligibility_preview_counts_without_scoring() -> None:
    """Cheap gate-only counts, so an officer learns their criteria are too narrow."""
    pool = [
        candidate(trainer_id=1, force_number="41001"),
        candidate(trainer_id=2, force_number="41002", availability_status="UNAVAILABLE"),
        candidate(trainer_id=3, force_number="41003", proficiency_score_in_required_area=None),
        candidate(trainer_id=4, force_number="41004", proficiency_score_in_required_area=None),
    ]
    preview = preview_eligibility(programme(), pool)
    assert preview.eligible == 1
    assert preview.total == 4
    assert preview.by_reason["MISSING_SPECIALIZATION"] == 2
    assert preview.by_reason["UNAVAILABLE"] == 1


# --- Decimal discipline (B10) ---------------------------------------------


def test_scores_are_exact_decimals_not_floats() -> None:
    """Float drift in an allocation record would make it non-reproducible."""
    scored = score_candidate(
        candidate(), programme(), STANDARD_WEIGHTS, today=TODAY, prior_mean=DEFAULT_PRIOR_MEAN
    )
    assert isinstance(scored.total, Decimal)
    for item in scored.breakdown:
        assert isinstance(item.normalized, Decimal)
        assert isinstance(item.contribution, Decimal)
        assert item.normalized == item.normalized.quantize(Decimal("0.01"))


def test_repeated_scoring_reproduces_byte_identical_totals() -> None:
    """The property that makes a decision auditable years later."""
    totals = {
        score_candidate(
            candidate(), programme(), STANDARD_WEIGHTS, today=TODAY, prior_mean=DEFAULT_PRIOR_MEAN
        ).total
        for _ in range(50)
    }
    assert len(totals) == 1


# --- Defensive branches ---------------------------------------------------


def test_specialisation_scores_zero_if_reached_without_the_discipline() -> None:
    """Defensive path: BR-04 should gate this out, but the criterion must not crash.

    Exercised directly because the engine can never reach it — which is exactly why
    it needs a test. An unreachable branch that raises is a latent crash waiting for
    the day someone reorders the gates.
    """
    normalized, raw, explanation, quality = CRITERIA[CriterionKey.SPECIALIZATION].score(
        candidate(proficiency_score_in_required_area=None), programme(), DEFAULT_PRIOR_MEAN
    )
    assert normalized == Decimal("0")
    assert raw == "No matching specialisation"
    assert quality is DataQuality.MISSING
    assert "Cybercrime Investigation" in explanation


def test_unknown_criterion_key_is_rejected() -> None:
    """A weight for a criterion that does not exist is a caller error, not a default."""

    class Fake:
        value = "TELEPATHY"

    with pytest.raises(WeightsError, match="Unknown scoring criteria"):
        validate_weights({Fake(): Decimal("100")})  # type: ignore[dict-item]


def test_criterion_score_serialises_for_jsonb() -> None:
    """The Score Ledger payload is camelCase and JSON-safe at the storage boundary."""
    scored = score_candidate(
        candidate(), programme(), STANDARD_WEIGHTS, today=TODAY, prior_mean=DEFAULT_PRIOR_MEAN
    )
    payload = scored.breakdown[0].to_json()
    assert payload["key"] == "SPECIALIZATION"
    assert payload["label"] == "Specialisation match"
    assert payload["dataQuality"] == "COMPLETE"
    assert set(payload) == {
        "key",
        "label",
        "weight",
        "rawValue",
        "normalized",
        "contribution",
        "explanation",
        "dataQuality",
    }


def test_evaluation_counterfactual_always_names_a_threshold() -> None:
    """The evaluation lever states the rating needed, never a bare suggestion.

    A rating of 1.0 can never raise a mean that already blends in the prior, so
    "with one further evaluation" without a threshold would be an unreachable
    sentence. It is not emitted at all.
    """
    leader = candidate(
        trainer_id=1,
        force_number="41001",
        evaluation_count=6,
        evaluation_mean=Decimal("4.8"),
        evaluation_count_in_area=6,
        evaluation_mean_in_area=Decimal("4.8"),
    )
    trailer = candidate(
        trainer_id=2,
        force_number="41002",
        evaluation_count=4,
        evaluation_mean=Decimal("4.0"),
        evaluation_count_in_area=4,
        evaluation_mean_in_area=Decimal("4.0"),
    )
    result = generate_prediction(programme(), [leader, trailer], STANDARD_WEIGHTS, today=TODAY)
    second = result.predictions[1]
    if second.counterfactual is not None and "evaluation" in second.counterfactual:
        assert "or above" in second.counterfactual
        rating = Decimal(second.counterfactual.split("at ")[1].split(" ")[0])
        assert Decimal("1.0") < rating <= Decimal("5.0")


def test_counterfactual_can_reach_the_proficiency_lever() -> None:
    """Lever 3: when performance and experience cannot close the gap, proficiency may.

    Constructed with PERFORMANCE and EXPERIENCE weighted to zero, so the search is
    forced past the first two levers.
    """
    weights = {
        CriterionKey.SPECIALIZATION: Decimal("60"),
        CriterionKey.PERFORMANCE: Decimal("0"),
        CriterionKey.EXPERIENCE: Decimal("0"),
        CriterionKey.QUALIFICATION: Decimal("30"),
        CriterionKey.AVAILABILITY: Decimal("10"),
    }
    leader = candidate(trainer_id=1, force_number="41001")
    trailer = candidate(
        trainer_id=2,
        force_number="41002",
        proficiency_score_in_required_area=Decimal("85"),
        proficiency_name_in_required_area="Advanced",
    )
    result = generate_prediction(programme(), [leader, trailer], weights, today=TODAY)
    second = result.predictions[1]
    assert second.counterfactual is not None
    assert "proficiency" in second.counterfactual


def test_counterfactual_is_none_when_tied_on_score() -> None:
    """A candidate who lost only on the tie-break cannot be advised to improve."""
    a = candidate(trainer_id=1, force_number="41001")
    b = candidate(trainer_id=2, force_number="41002")
    result = generate_prediction(programme(), [a, b], STANDARD_WEIGHTS, today=TODAY)
    assert result.predictions[0].total == result.predictions[1].total
    assert result.predictions[1].counterfactual is None
