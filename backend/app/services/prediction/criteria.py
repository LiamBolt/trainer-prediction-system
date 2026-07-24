"""Stage 2 — criterion scoring (§5.4, §5.5).

One class per criterion implementing the :class:`Criterion` protocol, registered in a
dictionary keyed by ``criterion_key``. **Adding a sixth criterion means adding a class
here and a row in `scoring_policy_weights` — no migration, no change to the engine.**
That is NFR-10 discharged rather than asserted.

Each criterion normalises to 0-100 and knows nothing about weights; weighting and
summation happen in :mod:`app.services.prediction.engine`. Keeping normalisation and
weighting separate is what lets the Weight Studio re-rank instantly: changing a weight
never changes a ``normalized`` value, only its ``contribution``.

All arithmetic is :class:`~decimal.Decimal` with ``ROUND_HALF_UP`` (B10).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.models.enums import CriterionKey, DataQuality
from app.services.prediction.types import (
    CandidateFacts,
    ProgrammeRequirements,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")

#: Years of service at which EXPERIENCE saturates. Twenty years is the ceiling because
#: beyond it more service does not make a better instructor — a thirty-year veteran and
#: a twenty-year one are both simply experienced, and scaling linearly to the maximum
#: observed would let one unusually long-serving officer compress everyone else.
EXPERIENCE_CEILING_YEARS = Decimal("20")

#: Bonus when a second specialisation shares the programme's discipline group.
BREADTH_BONUS = Decimal("10")

#: Bonus for a qualification from a police training institution. UPF-specific pedagogy
#: is worth more to a UPF course than a generic degree of the same academic level.
POLICE_INSTITUTION_BONUS = Decimal("8")

#: Each concurrent allocation costs this much availability.
ALLOCATION_PENALTY = Decimal("25")

#: Ceiling applied when a trainer is ASSIGNED rather than AVAILABLE.
ASSIGNED_CEILING = Decimal("50")

#: Shrinkage strength: the prior carries the weight of this many observations (§5.5).
SHRINKAGE_K = Decimal("3")

#: Prior used when the system holds no evaluations at all.
DEFAULT_PRIOR_MEAN = Decimal("3.2")

#: Evaluations in the programme's own discipline are preferred, but only once there
#: are at least this many — below it the sample is too small to beat the full history.
RELEVANT_EVALUATION_MINIMUM = 2


def quantise(value: Decimal) -> Decimal:
    """Round to two decimal places, half away from zero.

    ``ROUND_HALF_UP`` rather than Python's default banker's rounding: an officer
    checking 87.005 expects 87.01, and "the system rounds to even" is not an
    explanation anyone should have to give about an allocation decision.

    Args:
        value: The value to round.

    Returns:
        The value quantised to 0.01.
    """
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def clamp(value: Decimal) -> Decimal:
    """Clamp to the 0-100 range and quantise.

    Args:
        value: The raw normalised value.

    Returns:
        A value in [0, 100] with two decimal places.
    """
    return quantise(max(ZERO, min(HUNDRED, value)))


class Criterion(Protocol):
    """A scoring criterion.

    Structural rather than inherited, so a criterion is anything with the right
    ``key`` and ``score``; a test can substitute a stub without importing a base class.
    """

    key: CriterionKey
    label: str

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Normalise this criterion for one candidate.

        Args:
            facts: The candidate.
            programme: The requirements.
            prior_mean: The shrinkage prior for this run.

        Returns:
            ``(normalized, raw_value, explanation, data_quality)``.
        """
        ...


class SpecializationCriterion:
    """How closely the trainer's proven expertise matches what the course requires.

    Base score is the proficiency level's value from ``proficiency_levels`` — read
    from the database, not hard-coded, so policy can be retuned with an UPDATE
    (NFR-10). A breadth bonus applies when a *second* specialisation falls in the same
    discipline group, which is evidence of adjacent competence rather than a narrow
    specialist.
    """

    key = CriterionKey.SPECIALIZATION
    label = "Specialisation match"

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Score the specialisation match."""
        _ = prior_mean
        base = facts.proficiency_score_in_required_area
        if base is None:
            # Defensive: BR-04 should have gated this candidate out already.
            return (
                ZERO,
                "No matching specialisation",
                f"Holds no specialisation in {programme.required_specialization_name}.",
                DataQuality.MISSING,
            )

        proficiency = facts.proficiency_name_in_required_area or "Recorded"
        bonus = BREADTH_BONUS if facts.has_group_matching_specialisation else ZERO
        note = (
            f" A second specialisation also fits the {programme.discipline_group} group."
            if facts.has_group_matching_specialisation and programme.discipline_group
            else ""
        )
        return (
            clamp(base + bonus),
            f"{proficiency} · {programme.required_specialization_name}",
            (f"Holds {proficiency} proficiency in {programme.required_specialization_name}.{note}"),
            DataQuality.COMPLETE,
        )


class PerformanceCriterion:
    """Proven performance, via Bayesian shrinkage toward a prior (§5.5).

    The two naive options are both wrong. Scoring an unevaluated trainer **zero**
    punishes them for the system's newness, which at launch means punishing everyone.
    Using a **raw mean** lets a single lucky 5.0 outrank a veteran averaging 4.6 over
    twelve courses.

    Shrinkage solves both::

        adjusted_mean = (n × observed_mean + k × prior_mean) / (n + k)
        normalized    = (adjusted_mean − 1) / 4 × 100

    with ``k = 3``, so the prior carries the weight of three observations.

    Properties worth knowing, because they are what make the estimator defensible:

    - At ``n = 0`` it returns exactly the prior. With the default prior of 3.2 that is
      55.0 normalised, matching the frontend's existing flat behaviour — the flat 55 is
      a strict special case of this formula, not a competing rule.
    - At ``n = 1`` the trainer moves a quarter of the way toward their own evidence.
    - By ``n = 12`` the prior is nearly irrelevant.
    - It is **monotonic and continuous**, so a newly recorded evaluation never causes a
      discontinuous jump in rank. That matters operationally: an officer who watches a
      trainer leap five places after one evaluation stops trusting the system.

    Evaluations within the programme's own discipline group are preferred, but only
    once there are at least two of them.
    """

    key = CriterionKey.PERFORMANCE
    label = "Proven performance"

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Score performance with shrinkage."""
        use_area = (
            facts.evaluation_count_in_area >= RELEVANT_EVALUATION_MINIMUM
            and facts.evaluation_mean_in_area is not None
        )
        if use_area:
            count = facts.evaluation_count_in_area
            observed = facts.evaluation_mean_in_area
            scope = f"{(programme.discipline_group or 'related').lower()} courses"
        else:
            count = facts.evaluation_count
            observed = facts.evaluation_mean
            scope = "all recorded courses"

        n = Decimal(count)
        observed_mean = observed if observed is not None else prior_mean
        adjusted = (n * observed_mean + SHRINKAGE_K * prior_mean) / (n + SHRINKAGE_K)
        normalized = clamp((adjusted - Decimal("1")) / Decimal("4") * HUNDRED)

        if count == 0:
            return (
                normalized,
                "No evaluations recorded",
                (
                    "No past evaluations exist yet, so a neutral starting point was used "
                    "rather than a zero. This ranking rests on qualifications and "
                    "availability."
                ),
                DataQuality.MISSING,
            )

        quality = DataQuality.PARTIAL if count < 3 else DataQuality.COMPLETE
        plural = "" if count == 1 else "s"
        shown = observed_mean.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        caveat = (
            " Adjusted toward the service average because the record is still short."
            if count < 3
            else ""
        )
        return (
            normalized,
            f"{shown} of 5 · {count} evaluation{plural}",
            f"Averaged {shown} out of 5 across {count} {scope}.{caveat}",
            quality,
        )


class ExperienceCriterion:
    """Years of service, capped at a twenty-year ceiling."""

    key = CriterionKey.EXPERIENCE
    label = "Years of service"

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Score years of service."""
        _ = (programme, prior_mean)
        years = Decimal(facts.years_experience)
        ratio = min(years / EXPERIENCE_CEILING_YEARS, Decimal("1"))
        plural = "" if facts.years_experience == 1 else "s"
        return (
            clamp(ratio * HUNDRED),
            f"{facts.years_experience} year{plural}",
            (
                f"Has {facts.years_experience} year{plural} of service "
                f"({EXPERIENCE_CEILING_YEARS:.0f} years is the ceiling)."
            ),
            DataQuality.COMPLETE,
        )


class QualificationCriterion:
    """Highest formal qualification, with a bonus for police-college training.

    The bonus is driven by ``institutions.institution_type = 'POLICE'``, a column —
    not by matching institution *names* as the frontend currently does. A newly added
    police school therefore qualifies automatically rather than on the day someone
    remembers to edit a constant.
    """

    key = CriterionKey.QUALIFICATION
    label = "Qualification"

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Score the highest qualification."""
        _ = (programme, prior_mean)
        base = facts.highest_qualification_score
        if base is None:
            return (
                ZERO,
                "None recorded",
                "No formal qualification is on record.",
                DataQuality.MISSING,
            )
        bonus = POLICE_INSTITUTION_BONUS if facts.has_police_institution_qualification else ZERO
        name = facts.highest_qualification_name or "Recorded qualification"
        note = " from a police training institution" if bonus else ""
        return (
            clamp(base + bonus),
            name,
            f"Highest qualification is a {name.lower()}{note}.",
            DataQuality.COMPLETE,
        )


class AvailabilityCriterion:
    """Spare teaching capacity — not a gate, a preference.

    Each concurrent allocation costs 25 points, and an ``ASSIGNED`` trainer is capped
    at 50 regardless. This is the criterion that surfaces over-reliance on a few
    familiar names, which is the pattern the SRS problem statement is about: without
    it, the best-qualified trainer wins every course until they are unavailable.
    """

    key = CriterionKey.AVAILABILITY
    label = "Availability"

    def score(
        self, facts: CandidateFacts, programme: ProgrammeRequirements, prior_mean: Decimal
    ) -> tuple[Decimal, str, str, DataQuality]:
        """Score current spare capacity."""
        _ = (programme, prior_mean)
        load = Decimal(facts.active_allocation_count)
        normalized = max(ZERO, HUNDRED - ALLOCATION_PENALTY * load)
        if facts.availability_status == "ASSIGNED":
            normalized = min(normalized, ASSIGNED_CEILING)

        if facts.active_allocation_count == 0:
            description = "no current allocations"
        else:
            plural = "" if facts.active_allocation_count == 1 else "s"
            description = f"{facts.active_allocation_count} current allocation{plural}"
        state = "Assigned" if facts.availability_status == "ASSIGNED" else "Available"
        return (
            clamp(normalized),
            f"{state} · {description}",
            f"Currently has {description}.",
            DataQuality.COMPLETE,
        )


#: The registry. A sixth criterion is added here and given a weight row — nothing else
#: in the engine changes, and no migration is required (NFR-10, §5.4).
CRITERIA: dict[CriterionKey, Criterion] = {
    CriterionKey.SPECIALIZATION: SpecializationCriterion(),
    CriterionKey.PERFORMANCE: PerformanceCriterion(),
    CriterionKey.EXPERIENCE: ExperienceCriterion(),
    CriterionKey.QUALIFICATION: QualificationCriterion(),
    CriterionKey.AVAILABILITY: AvailabilityCriterion(),
}

#: Display order for the Score Ledger — heaviest default weight first.
CRITERION_ORDER: tuple[CriterionKey, ...] = (
    CriterionKey.SPECIALIZATION,
    CriterionKey.PERFORMANCE,
    CriterionKey.EXPERIENCE,
    CriterionKey.QUALIFICATION,
    CriterionKey.AVAILABILITY,
)


def shrunk_mean(count: int, observed_mean: Decimal | None, prior_mean: Decimal) -> Decimal:
    """Apply shrinkage to an observed mean (§5.5).

    Exposed separately from :class:`PerformanceCriterion` because the tie-break and
    the counterfactual search both need the same number, and computing it twice by
    two routes is how the two quietly disagree.

    Args:
        count: Number of observations.
        observed_mean: Their mean, or None when there are none.
        prior_mean: The prior to shrink toward.

    Returns:
        The shrunk mean, on the original 1-5 scale.

    Example:
        >>> shrunk_mean(0, None, Decimal("3.2"))
        Decimal('3.2')
    """
    n = Decimal(count)
    observed = observed_mean if observed_mean is not None else prior_mean
    return (n * observed + SHRINKAGE_K * prior_mean) / (n + SHRINKAGE_K)
