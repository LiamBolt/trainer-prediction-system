"""Scoring policy schemas (§6.6, NFR-10)."""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.schemas.base import CamelModel, ScoreField


class WeightRead(CamelModel):
    """One criterion's weight under a policy."""

    criterion_key: str
    display_label: str
    weight: ScoreField
    description: str = Field(description="Plain-English explanation shown in the Weight Studio.")
    sort_order: int


class ScoringPolicyRead(CamelModel):
    """A scoring policy version."""

    policy_id: int
    version: int
    name: str
    is_active: bool
    effective_from: datetime.datetime
    notes: str | None = None
    created_by: int | None = None
    created_by_name: str | None = None
    weights: list[WeightRead] = Field(default_factory=list)


class WeightInput(CamelModel):
    """One criterion's weight in a policy update."""

    criterion_key: str = Field(
        pattern="^(SPECIALIZATION|QUALIFICATION|EXPERIENCE|PERFORMANCE|AVAILABILITY)$"
    )
    weight: Decimal = Field(ge=0, le=100, decimal_places=2)


class ScoringPolicyUpdate(CamelModel):
    """Saving a new policy version (NFR-10).

    Creates a **new version** and deactivates the previous one; it never mutates in
    place. Historical prediction runs stay interpretable against the weights that
    actually produced them, which is what makes an old decision defensible.
    """

    weights: list[WeightInput] = Field(min_length=1)
    name: str = Field(default="Revised policy", min_length=3, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check_total(self) -> ScoringPolicyUpdate:
        """Refuse weights that do not total exactly 100.

        Checked here, in the service, and by a deferred database trigger. Three layers
        because a score computed on a scale that is not 0-100 is silently wrong
        everywhere it is displayed.
        """
        keys = [w.criterion_key for w in self.weights]
        if len(keys) != len(set(keys)):
            raise ValueError("Each criterion may appear only once.")
        total = sum((w.weight for w in self.weights), start=Decimal("0"))
        if total != Decimal("100"):
            raise ValueError(f"The weights must total 100, but they total {total}.")
        return self
