"""Confidence — how much the system knows about a trainer (§5.6).

**Confidence is data completeness, not likelihood of success.** A trainer with an
excellent record and a thin profile scores low confidence; one with a complete profile
and mediocre ratings scores high. It says how much evidence the score rests on, and
nothing at all about whether the trainer will teach well.

This is the single most misreadable number on the screen, so it is stated in the
docstring, in the API description, and in the field description. An officer who reads
"LOW confidence" as "likely to fail" will make exactly the wrong decision about a
capable person the system happens to know little about.

::

    confidence       = 0.45 × evaluation_depth + 0.35 × profile_completeness
                       + 0.20 × recency
    evaluation_depth = min(n / 5, 1) × 100
    recency          = 100 × exp(−ln(2) × months_since_last / 18), floored at 40
"""

from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.models.enums import ConfidenceBand
from app.services.prediction.types import CandidateFacts

#: Weightings of the three components. They sum to 1.
DEPTH_WEIGHT = Decimal("0.45")
PROFILE_WEIGHT = Decimal("0.35")
RECENCY_WEIGHT = Decimal("0.20")

#: Evaluations at which depth saturates. Five is enough to characterise a trainer;
#: a sixth adds little, and rewarding volume indefinitely would favour whoever has
#: been asked most often — the very bias the availability criterion exists to counter.
DEPTH_TARGET = Decimal("5")

#: Half-life of evidence, in months. Exponential rather than linear decay because a
#: two-year-old evaluation is meaningfully staler than a six-month-old one, while a
#: four-year-old is not meaningfully staler than a three-year-old. Linear decay gets
#: both ends wrong.
RECENCY_HALF_LIFE_MONTHS = Decimal("18")

#: Recency never falls below this. Old-but-real evidence is not the same as no
#: evidence, and a floor of zero would rank a long-serving instructor with a five-year
#: record below someone the system has never seen.
RECENCY_FLOOR = Decimal("40")

#: Recency for a trainer with no evaluations at all.
RECENCY_NO_HISTORY = Decimal("40")

DAYS_PER_MONTH = Decimal("30.4375")

HIGH_THRESHOLD = 75
MODERATE_THRESHOLD = 45


def _exp_decay(months: Decimal) -> Decimal:
    """Compute ``exp(−ln(2) × months / half_life)`` in exact decimal arithmetic.

    Uses :meth:`decimal.Decimal.ln` and :meth:`decimal.Decimal.exp` rather than the
    ``math`` module, because ``math.exp`` returns a float and B10 forbids float
    anywhere in this package. The decimal context carries enough precision that the
    result is stable across platforms — which matters, since a confidence band that
    differs between two machines would make a run non-reproducible.

    Args:
        months: Months elapsed. Must be non-negative.

    Returns:
        The decay factor in (0, 1].
    """
    if months <= 0:
        return Decimal("1")
    exponent = -(Decimal("2").ln() * months / RECENCY_HALF_LIFE_MONTHS)
    return exponent.exp()


def compute_recency(last_evaluation_date: datetime.date | None, today: datetime.date) -> Decimal:
    """Score how recent a trainer's most recent evaluation is.

    Args:
        last_evaluation_date: The most recent evaluation, or None.
        today: Reference date, injected so tests are deterministic.

    Returns:
        A value between :data:`RECENCY_FLOOR` and 100.
    """
    if last_evaluation_date is None:
        return RECENCY_NO_HISTORY
    days = Decimal(max(0, (today - last_evaluation_date).days))
    months = days / DAYS_PER_MONTH
    decayed = Decimal("100") * _exp_decay(months)
    return max(RECENCY_FLOOR, decayed)


def band_for(level: int) -> ConfidenceBand:
    """Return the band for a confidence level.

    Args:
        level: 0-100.

    Returns:
        ``HIGH`` at 75 and above, ``MODERATE`` from 45, otherwise ``LOW``.
    """
    if level >= HIGH_THRESHOLD:
        return ConfidenceBand.HIGH
    if level >= MODERATE_THRESHOLD:
        return ConfidenceBand.MODERATE
    return ConfidenceBand.LOW


def compute_confidence(facts: CandidateFacts, today: datetime.date) -> tuple[int, ConfidenceBand]:
    """Compute a candidate's confidence level and band.

    Args:
        facts: The candidate.
        today: Reference date for the recency decay.

    Returns:
        The 0-100 level and its band.

    Example:
        A trainer with no evaluations and a 70% complete profile scores
        ``0.45×0 + 0.35×70 + 0.20×40 = 32.5`` → 33, which is ``LOW``. That is the
        honest answer: the system knows very little about them.
    """
    depth = min(Decimal(facts.evaluation_count) / DEPTH_TARGET, Decimal("1")) * Decimal("100")
    profile = Decimal(facts.profile_completeness)
    recency = compute_recency(facts.last_evaluation_date, today)

    raw = DEPTH_WEIGHT * depth + PROFILE_WEIGHT * profile + RECENCY_WEIGHT * recency
    level = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    level = max(0, min(100, level))
    return level, band_for(level)
