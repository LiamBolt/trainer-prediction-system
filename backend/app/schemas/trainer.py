"""Trainer schemas (§6.3).

Field names match ``frontend/src/types/domain.ts`` exactly. Where §6 and the frontend
disagree on a path, §6 wins; where they disagree on a **field name**, the frontend
wins, because it is already implemented against these shapes.
"""

from __future__ import annotations

import datetime

from pydantic import Field, model_validator

from app.schemas.base import CamelModel, OptionalRatingField, RatingField


class QualificationRead(CamelModel):
    """A qualification held by a trainer."""

    qualification_id: int
    trainer_id: int
    qualification_name: str
    qualification_level: str = Field(description="Level code, e.g. MASTERS.")
    level_id: int
    institution_name: str
    institution_id: int
    year_obtained: int


class SpecializationRead(CamelModel):
    """A discipline a trainer is proficient in."""

    specialization_id: int
    trainer_id: int
    specialization_area: str = Field(description="Discipline name, e.g. Cybercrime Investigation.")
    specialization_area_id: int
    proficiency_level: str = Field(description="Level code, e.g. ADVANCED.")
    proficiency_level_id: int
    years_in_area: int | None = None


class UnavailabilityRead(CamelModel):
    """A declared absence window."""

    unavailability_id: int
    trainer_id: int
    start_date: datetime.date
    end_date: datetime.date
    reason: str
    category: str


class EvaluationSummary(CamelModel):
    """One evaluation in a trainer's history."""

    evaluation_id: int
    allocation_id: int
    trainer_id: int
    programme_id: int
    programme_title: str
    score_awarded: RatingField
    evaluator_comments: str
    evaluated_by: int
    evaluated_by_name: str
    evaluation_date: datetime.date


class TrainerSummary(CamelModel):
    """A trainer as shown in the directory list.

    A projection: twelve columns, no relationships. Hydrating 812 ORM entities with
    their qualifications to render a table would fetch several thousand rows to
    display twelve columns.
    """

    trainer_id: int
    user_id: int
    full_name: str
    force_number: str
    police_rank: str
    station: str
    region: str
    directorate: str
    years_experience: int
    availability_status: str
    contact_number: str
    profile_completeness: int


class TrainerDetail(TrainerSummary):
    """A trainer's full profile, with credentials and history."""

    date_of_enlistment: datetime.date | None = None
    bio: str | None = None
    qualifications: list[QualificationRead] = Field(default_factory=list)
    specializations: list[SpecializationRead] = Field(default_factory=list)
    unavailability: list[UnavailabilityRead] = Field(default_factory=list)
    performance_history: list[EvaluationSummary] = Field(default_factory=list)
    current_allocations: int = 0
    last_assigned_date: datetime.datetime | None = None
    mean_score: OptionalRatingField = None


class TrainerSelfUpdate(CamelModel):
    """A trainer editing their own profile (FR-02).

    Rank, station, and contact number **cannot be set empty** — §6.3 requires a 422
    naming the field rather than silently storing a blank where a phone number was.
    """

    rank_id: int | None = Field(default=None, gt=0, description="Police rank.")
    station_id: int | None = Field(default=None, gt=0, description="Posting.")
    years_experience: int | None = Field(default=None, ge=0, le=50)
    contact_number: str | None = Field(default=None, min_length=1, max_length=24)
    bio: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _reject_blank_contact(self) -> TrainerSelfUpdate:
        """Refuse a whitespace-only contact number.

        ``min_length`` alone accepts a single space, which stores as blank and reads
        as "no contact number" to every officer who later needs one.
        """
        if self.contact_number is not None and not self.contact_number.strip():
            raise ValueError("A contact number is required and cannot be blank.")
        return self


class AvailabilityUpdate(CamelModel):
    """A trainer changing their availability."""

    availability_status: str = Field(
        pattern="^(AVAILABLE|ASSIGNED|UNAVAILABLE)$",
        description="AVAILABLE, ASSIGNED, or UNAVAILABLE.",
        examples=["UNAVAILABLE"],
    )


class QualificationCreate(CamelModel):
    """Adding a qualification (FR-03). Appends; never overwrites."""

    qualification_name: str = Field(
        min_length=2, max_length=160, examples=["MSc, Criminal Justice"]
    )
    level_id: int = Field(gt=0)
    institution_id: int = Field(gt=0)
    year_obtained: int = Field(ge=1960, le=2100)


class SpecializationCreate(CamelModel):
    """Adding a specialisation (FR-03).

    ``proficiencyLevelId`` is required. §6.3 is explicit that a missing level is a 422
    rather than a defaulted BASIC: a defaulted proficiency would feed the scoring
    engine a number nobody stated.
    """

    specialization_area_id: int = Field(gt=0)
    proficiency_level_id: int = Field(gt=0, description="Required — never defaulted.")
    years_in_area: int | None = Field(default=None, ge=0, le=50)


class UnavailabilityCreate(CamelModel):
    """Declaring an absence window."""

    start_date: datetime.date
    end_date: datetime.date
    reason: str = Field(min_length=3, max_length=200)
    category: str = Field(pattern="^(LEAVE|COURT|DEPLOYMENT|STUDY|MEDICAL|OTHER)$")

    @model_validator(mode="after")
    def _check_dates(self) -> UnavailabilityCreate:
        """Refuse an end date before the start."""
        if self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date.")
        return self


class TrainerEvaluationsResponse(CamelModel):
    """A trainer's evaluation history with its mean."""

    evaluations: list[EvaluationSummary]
    mean: OptionalRatingField = None
