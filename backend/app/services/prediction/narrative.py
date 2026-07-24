"""Stage 4 — narrative generation (§5.7).

Two pieces of text, both of which an officer acts on.

**The rationale** names the two highest-contributing criteria in concrete terms. It is
template-driven and cites only evidence that exists; when there is no history it says
so plainly rather than papering over it.

**The counterfactual** states the smallest single change that would reach rank 1. It
is produced by exhaustive search over a bounded set of levers and is **never
fabricated**. A statement like "would rank first with one more evaluation" that is
arithmetically false is worse than silence, because an officer will act on it — they
will schedule an evaluation that does not, in fact, change anything.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.models.enums import CriterionKey
from app.services.prediction.criteria import (
    EXPERIENCE_CEILING_YEARS,
    SHRINKAGE_K,
    clamp,
)
from app.services.prediction.types import (
    CandidateFacts,
    CriterionScore,
    ProgrammeRequirements,
    ScoredCandidate,
)

ONE_PLACE = Decimal("0.1")
HUNDRED = Decimal("100")

#: Ranks that receive a counterfactual. Below rank 5 the gap is rarely closable by one
#: change, and offering one to rank 40 would be noise dressed as advice.
COUNTERFACTUAL_MIN_RANK = 2
COUNTERFACTUAL_MAX_RANK = 5

#: The best rating obtainable, bounding the "one more evaluation" lever.
MAX_RATING = Decimal("5.0")


def surname(full_name: str) -> str:
    """Return the last word of a name, as UPF usage addresses people.

    Args:
        full_name: e.g. ``"Grace Nabirye"``.

    Returns:
        e.g. ``"Nabirye"``.
    """
    parts = full_name.split()
    return parts[-1] if parts else full_name


def build_rationale(
    facts: CandidateFacts,
    programme: ProgrammeRequirements,
    breakdown: tuple[CriterionScore, ...],
) -> str:
    """Write the one-sentence justification shown beside a rank.

    The most important text in the product. An Administrator reads it before
    approving; a trainer reads it when told why they were selected; an auditor reads
    it a year later. It therefore states evidence, never conclusions.

    Args:
        facts: The candidate.
        programme: The requirements.
        breakdown: The scored criteria, used to find the strongest evidence.

    Returns:
        A single sentence.
    """
    name = f"{facts.rank_code} {surname(facts.full_name)}"
    proficiency = facts.proficiency_name_in_required_area or "recorded"
    spec = programme.required_specialization_name
    years = facts.years_experience
    year_word = "year" if years == 1 else "years"

    if facts.evaluation_count == 0:
        return (
            f"{name} holds {proficiency} proficiency in {spec} and has {years} "
            f"{year_word} of service, but has no recorded evaluations yet — so this "
            "ranking rests on qualifications and availability."
        )

    use_area = facts.evaluation_count_in_area >= 2 and facts.evaluation_mean_in_area is not None
    if use_area:
        count = facts.evaluation_count_in_area
        mean = facts.evaluation_mean_in_area
        scope = f"previous {spec.lower()} courses"
    else:
        count = facts.evaluation_count
        mean = facts.evaluation_mean
        scope = "previous courses"

    shown = (mean or Decimal("0")).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)
    plural = "" if count == 1 else "s"
    # "course" reads oddly with a scope phrase already plural; keep it grammatical.
    scope_text = scope if count != 1 else scope.replace("courses", "course")

    sentence = (
        f"{name} holds {proficiency} proficiency in {spec}, has {years} {year_word} of "
        f"service, and averaged {shown} out of 5 across {count} {scope_text}"
    )
    if count < 3:
        return sentence + f" — only {count} evaluation{plural}, so that average is provisional."
    return sentence + "."


def _performance_normalised(adjusted_mean: Decimal) -> Decimal:
    """Convert a 1-5 mean to the 0-100 PERFORMANCE scale."""
    return clamp((adjusted_mean - Decimal("1")) / Decimal("4") * HUNDRED)


def build_counterfactual(
    candidate: ScoredCandidate,
    top_total: Decimal,
    weights: dict[CriterionKey, Decimal],
    prior_mean: Decimal,
    programme: ProgrammeRequirements | None = None,
) -> str | None:
    """Find the smallest single change that would lift this candidate to rank 1.

    The search space is small and enumerable, so it is searched **exhaustively** rather
    than approximated — at three levers and at most twenty steps each, exhaustive
    search costs microseconds and removes any question of whether a better answer was
    missed.

    Levers, in order of how readily a training office can act on them:

    1. One further evaluation, solving for the minimum rating that closes the gap.
    2. Additional years of service, below the twenty-year ceiling.
    3. One proficiency level higher in the required discipline.

    Returns ``None`` when no single change suffices. That is the important case: it is
    what stops the system from making a promise it cannot keep.

    Args:
        candidate: The candidate, already scored and ranked 2-5.
        top_total: The rank-1 score to beat.
        weights: The weights in force.
        prior_mean: The shrinkage prior for this run.

    Returns:
        A sentence, or None.
    """
    needed = top_total - candidate.total
    if needed <= 0:
        # Already at or above the top score — lost on the tie-break alone, and no
        # amount of evidence changes a tie-break.
        return None

    facts = candidate.facts

    # --- Lever 1: one more evaluation. -------------------------------------
    weight = weights.get(CriterionKey.PERFORMANCE, Decimal("0"))
    if weight > 0:
        current = next(
            (c.normalized for c in candidate.breakdown if c.key == CriterionKey.PERFORMANCE),
            Decimal("0"),
        )
        use_area = facts.evaluation_count_in_area >= 2 and facts.evaluation_mean_in_area is not None
        count = facts.evaluation_count_in_area if use_area else facts.evaluation_count
        observed = facts.evaluation_mean_in_area if use_area else facts.evaluation_mean

        # Solve for the rating s that closes the gap, then confirm by recomputing —
        # never trust the algebra alone, because an off-by-one in the shrinkage terms
        # would produce a confident, false statement.
        best: Decimal | None = None
        candidate_rating = Decimal("1.0")
        while candidate_rating <= MAX_RATING:
            n = Decimal(count)
            total_observed = (observed if observed is not None else prior_mean) * n
            new_mean = (total_observed + candidate_rating + SHRINKAGE_K * prior_mean) / (
                n + Decimal("1") + SHRINKAGE_K
            )
            gain = weight * (_performance_normalised(new_mean) - current) / HUNDRED
            if gain >= needed:
                best = candidate_rating
                break
            candidate_rating += ONE_PLACE

        if best is not None:
            # The threshold is always named. A bare "with one further evaluation"
            # would need a rating of 1.0 to suffice, and the minimum possible rating
            # can never *raise* a mean that already blends in the prior — so that
            # phrasing would be unreachable, and a sentence that cannot occur is
            # worse than no sentence: it invites a reader to assume it can.
            shown = best.quantize(ONE_PLACE, rounding=ROUND_CEILING)
            return f"Would rank 1st with one further evaluation at {shown} or above."

    # --- Lever 2: more years of service. -----------------------------------
    weight = weights.get(CriterionKey.EXPERIENCE, Decimal("0"))
    if weight > 0 and Decimal(facts.years_experience) < EXPERIENCE_CEILING_YEARS:
        current = next(
            (c.normalized for c in candidate.breakdown if c.key == CriterionKey.EXPERIENCE),
            Decimal("0"),
        )
        extra = 1
        while Decimal(facts.years_experience + extra) <= EXPERIENCE_CEILING_YEARS:
            new_years = Decimal(facts.years_experience + extra)
            new_norm = clamp(min(new_years / EXPERIENCE_CEILING_YEARS, Decimal("1")) * HUNDRED)
            gain = weight * (new_norm - current) / HUNDRED
            if gain >= needed:
                plural = "" if extra == 1 else "s"
                return f"Would rank 1st with {extra} more year{plural} of service."
            extra += 1

    # --- Lever 3: one proficiency level higher. ----------------------------
    weight = weights.get(CriterionKey.SPECIALIZATION, Decimal("0"))
    current_score = facts.proficiency_score_in_required_area
    if weight > 0 and current_score is not None:
        current = next(
            (c.normalized for c in candidate.breakdown if c.key == CriterionKey.SPECIALIZATION),
            Decimal("0"),
        )
        # Proficiency values come from the database; the next level up is not knowable
        # here without a lookup, so the largest possible step — to 100 — bounds it. If
        # even that does not close the gap, no proficiency change will.
        best_possible = clamp(HUNDRED + (current - current_score))
        gain = weight * (best_possible - current) / HUNDRED
        if gain >= needed:
            # Name the *discipline*, not the trainer's current level. "A higher
            # proficiency in Advanced" is not a sentence anyone can act on.
            discipline = (
                programme.required_specialization_name
                if programme is not None
                else "the required discipline"
            )
            return f"Would rank 1st with a higher recorded proficiency in {discipline}."

    return None
