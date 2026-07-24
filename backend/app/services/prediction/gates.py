"""Stage 1 — hard gates. Elimination, not scoring (§5.3).

Five rules, applied **in this order**, and the *first* failure is the reason recorded.
Order matters because the reason is shown to an officer: a trainer who is both
unavailable and under-qualified should be reported as unavailable, because that is the
fact that settles it and the one they can act on.

Excluded trainers never appear in the ranked list — not greyed out, not at the bottom,
**absent** (BR-03). They appear instead in the Exclusion Ledger, which is what lets the
system answer "why isn't so-and-so on the list?" without a phone call.

Every ``reason_detail`` is a sentence a non-technical officer reads verbatim:
*"Assigned to Digital Forensics Level 2, 10-21 Aug 2026"* — never *"conflict=true"*.
"""

from __future__ import annotations

import datetime

from app.models.enums import AvailabilityStatus, BusinessRule, ExclusionReason
from app.services.prediction.types import CandidateFacts, Exclusion, ProgrammeRequirements

#: Which rule each reason cites. Kept beside the gates so a new reason cannot be added
#: without deciding, explicitly, which rule justifies it.
BUSINESS_RULE_FOR: dict[ExclusionReason, BusinessRule] = {
    ExclusionReason.UNAVAILABLE: BusinessRule.BR_03,
    ExclusionReason.SCHEDULE_CONFLICT: BusinessRule.BR_03,
    ExclusionReason.MISSING_SPECIALIZATION: BusinessRule.BR_04,
    ExclusionReason.BELOW_MINIMUM_EXPERIENCE: BusinessRule.FR_05,
    ExclusionReason.BELOW_MINIMUM_QUALIFICATION: BusinessRule.FR_05,
}


def format_date_range(start: datetime.date, end: datetime.date) -> str:
    """Format a date range the way a UPF signal would write it.

    Args:
        start: First day.
        end: Last day.

    Returns:
        e.g. ``"10-21 Aug 2026"``, or ``"28 Jul - 3 Aug 2026"`` across a month.
    """
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{end.day} {start:%b %Y}"
    if start.year == end.year:
        return f"{start.day} {start:%b} - {end.day} {end:%b %Y}"
    return f"{start:%d %b %Y} - {end:%d %b %Y}"


def evaluate_gates(facts: CandidateFacts, programme: ProgrammeRequirements) -> Exclusion | None:
    """Apply every hard gate to one candidate.

    Implements BR-03, BR-04, and FR-05.

    Args:
        facts: The candidate.
        programme: The requirements being staffed against.

    Returns:
        An :class:`Exclusion` describing the first failed gate, or None if the
        candidate passes all five.
    """
    # 1 — declared unavailable (BR-03).
    if facts.availability_status == AvailabilityStatus.UNAVAILABLE:
        return _exclude(
            facts,
            ExclusionReason.UNAVAILABLE,
            "Marked unavailable for assignment.",
        )

    # 2 — lacks the required specialisation (BR-04). A NULL proficiency score is
    # precisely "does not hold this discipline"; the facts query returns None rather
    # than zero so the two cases stay distinguishable.
    if facts.proficiency_score_in_required_area is None:
        return _exclude(
            facts,
            ExclusionReason.MISSING_SPECIALIZATION,
            f"Does not hold the required specialisation ({programme.required_specialization_name}).",
        )

    # 3 — already committed for these dates (BR-03). Covers both a confirmed
    # allocation and a declared absence window; the message names which.
    if facts.conflict is not None:
        conflict = facts.conflict
        window = format_date_range(conflict.start_date, conflict.end_date)
        if conflict.kind == "UNAVAILABILITY":
            detail = f"Unavailable: {conflict.title} · {window}."
        else:
            detail = f"Assigned to {conflict.title} · {window}."
        return _exclude(facts, ExclusionReason.SCHEDULE_CONFLICT, detail)

    # 4 — below the minimum years of service (FR-05).
    if facts.years_experience < programme.minimum_experience:
        return _exclude(
            facts,
            ExclusionReason.BELOW_MINIMUM_EXPERIENCE,
            f"{facts.years_experience} years of service; {programme.minimum_experience} required.",
        )

    # 5 — below the minimum qualification, when one is set (FR-05).
    if programme.minimum_qualification_order is not None:
        held_order = facts.highest_qualification_order
        if held_order is None or held_order < programme.minimum_qualification_order:
            held = (
                facts.highest_qualification_name.lower()
                if facts.highest_qualification_name
                else "no formal qualification"
            )
            required = (programme.minimum_qualification_name or "a higher qualification").lower()
            return _exclude(
                facts,
                ExclusionReason.BELOW_MINIMUM_QUALIFICATION,
                f"Highest qualification is {held}; {required} required.",
            )

    return None


def _exclude(facts: CandidateFacts, reason: ExclusionReason, detail: str) -> Exclusion:
    """Build an exclusion carrying the correct rule citation.

    Args:
        facts: The excluded candidate.
        reason: Why.
        detail: The officer-facing sentence.

    Returns:
        The exclusion record.
    """
    return Exclusion(
        trainer_id=facts.trainer_id,
        full_name=facts.full_name,
        rank_code=facts.rank_code,
        force_number=facts.force_number,
        reason=reason,
        reason_detail=detail,
        business_rule=BUSINESS_RULE_FOR[reason],
    )
