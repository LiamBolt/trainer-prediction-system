"""Training programme schemas (§6.4)."""

from __future__ import annotations

import datetime

from pydantic import Field, model_validator

from app.schemas.base import CamelModel


class ProgrammeSummary(CamelModel):
    """A programme as shown in a list."""

    programme_id: int
    registry_number: str
    title: str
    category: str
    category_id: int
    required_specialization: str | None = None
    required_specialization_area_id: int | None = None
    minimum_experience: int
    minimum_qualification: str | None = None
    minimum_qualification_level_id: int | None = None
    start_date: datetime.date
    end_date: datetime.date
    location: str = Field(description="Venue name.")
    station_id: int
    expected_participants: int | None = None
    status: str
    created_by: int
    created_by_name: str
    created_at: datetime.datetime
    requirements_set_at: datetime.datetime | None = None
    requirements_changed_since_prediction: bool = False


class ProgrammeStatusEvent(CamelModel):
    """One step in a programme's lifecycle, for the detail timeline."""

    status: str
    occurred_at: datetime.datetime
    actor_name: str | None = None
    detail: str


class ProgrammeRunSummary(CamelModel):
    """A one-line summary of a prediction run against this programme."""

    run_id: int
    generated_at: datetime.datetime
    generated_by_name: str
    ranked_count: int
    excluded_count: int
    candidate_pool_size: int
    elapsed_ms: int
    is_superseded: bool
    top_trainer_name: str | None = None
    top_score: float | None = None


class ProgrammeDetail(CamelModel):
    """A programme with its timeline and latest run."""

    programme: ProgrammeSummary
    has_run: bool = False
    latest_run: ProgrammeRunSummary | None = None
    allocation_count: int = 0
    timeline: list[ProgrammeStatusEvent] = Field(default_factory=list)


class ProgrammeCreate(CamelModel):
    """Raising a training request (FR-04).

    Requirements are deliberately **not** accepted here. FR-04 creates the request and
    FR-05 defines what it needs; keeping them apart is what makes the `DRAFT` →
    `REQUIREMENTS_SET` transition mean something rather than being a flag.
    """

    title: str = Field(min_length=5, max_length=200, examples=["Digital Forensics Level 2"])
    category_id: int = Field(gt=0)
    start_date: datetime.date
    end_date: datetime.date
    station_id: int = Field(gt=0, description="Venue.")
    expected_participants: int | None = Field(default=None, gt=0, le=1000)

    @model_validator(mode="after")
    def _check_dates(self) -> ProgrammeCreate:
        """Refuse an end date before the start."""
        if self.end_date < self.start_date:
            raise ValueError("The course cannot end before it starts.")
        return self


class ProgrammeUpdate(CamelModel):
    """Editing a programme's particulars."""

    title: str | None = Field(default=None, min_length=5, max_length=200)
    category_id: int | None = Field(default=None, gt=0)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    station_id: int | None = Field(default=None, gt=0)
    expected_participants: int | None = Field(default=None, gt=0, le=1000)

    @model_validator(mode="after")
    def _check_dates(self) -> ProgrammeUpdate:
        """Refuse an end date before the start when both are supplied."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The course cannot end before it starts.")
        return self


class RequirementsInput(CamelModel):
    """Defining what a programme needs (FR-05).

    ``requiredSpecializationAreaId`` is required. A programme without it cannot be
    predicted against — the engine would have nothing to match on and would rank the
    entire force.
    """

    required_specialization_area_id: int = Field(
        gt=0, description="Required. The discipline BR-04 matches against."
    )
    minimum_experience: int = Field(default=0, ge=0, le=50)
    minimum_qualification_level_id: int | None = Field(
        default=None, gt=0, description="Optional. NULL means no minimum."
    )


class EligibilityPreviewResponse(CamelModel):
    """Gate-only counts for the live requirements preview (§6.4).

    Lets an officer discover that their criteria are too narrow **before** spending a
    prediction run, rather than after staring at a list of three names.
    """

    eligible: int
    total: int
    by_reason: dict[str, int] = Field(
        default_factory=dict, description="Exclusion counts keyed by reason code."
    )
    message: str = Field(description="Plain-English summary, rendered under the form.")
