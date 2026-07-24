"""Evaluation DTOs (FR-10, §6.8).

Recording an evaluation is the one action in this system that changes future
predictions. The response says so in plain language, because an administrator entering
a score should know they are not filling in a form — they are altering how this trainer
ranks from now on.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.allocation import AllocationListItem
from app.schemas.base import CamelModel, RatingField


class EvaluationRead(CamelModel):
    """A recorded performance evaluation."""

    evaluation_id: int
    registry_number: str = Field(default="", description="e.g. 'TPS/EVL/2026/0088'.")
    allocation_id: int
    trainer_id: int
    trainer_name: str = ""
    programme_id: int
    programme_title: str = ""
    score_awarded: RatingField = Field(description="1.0 to 5.0, one decimal place.")
    evaluator_comments: str
    evaluated_by: int
    evaluated_by_name: str = ""
    evaluation_date: datetime.date


class EvaluationInput(CamelModel):
    """A new evaluation (FR-10).

    ``evaluatorComments`` has a **20-character minimum** because a bare number is not an
    evaluation: this text is what a trainer reads to understand a score that will follow
    them into every future ranking.
    """

    allocation_id: int = Field(gt=0)
    score_awarded: Decimal = Field(
        ge=Decimal("1.0"),
        le=Decimal("5.0"),
        decimal_places=1,
        description="1.0 to 5.0, one decimal place.",
    )
    evaluator_comments: str = Field(min_length=20, max_length=4000)
    evaluation_date: datetime.date = Field(
        description="Date of assessment, which may precede the date it was entered."
    )


class EvaluationRecorded(CamelModel):
    """The response to recording an evaluation.

    ``message`` states the consequence in words the frontend echoes verbatim:
    *"Recorded. This score now informs future rankings for IP Mugisha."*
    """

    evaluation: EvaluationRead
    message: str


class EvaluationsResponse(CamelModel):
    """The evaluations screen: what is owed, and what is done (§6.8)."""

    awaiting: list[AllocationListItem] = Field(
        default_factory=list,
        description="Allocations at CONDUCTED — training delivered, score not yet recorded.",
    )
    recorded: list[EvaluationRead] = Field(default_factory=list)


# A trainer's own history is already modelled by ``schemas.trainer``
# (``EvaluationSummary`` / ``TrainerEvaluationsResponse``) and is reused by
# ``GET /evaluations/trainer/{id}`` rather than restated here — two shapes for one
# concept is how the mean on one screen ends up disagreeing with the other.
