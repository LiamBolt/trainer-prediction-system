"""Reference-data response schemas (§6.2).

Every dropdown in the frontend is populated from these. They are read-only lookup
lists that change perhaps once a year, so they are cached and carry a
``Cache-Control`` header.
"""

from __future__ import annotations

from app.schemas.base import CamelModel, ScoreField


class RoleRef(CamelModel):
    """A system role."""

    role_id: int
    name: str
    display_name: str
    description: str | None = None


class RankRef(CamelModel):
    """A police rank. ``seniority_order`` is the orderable key — rank codes are not."""

    rank_id: int
    code: str
    full_name: str
    management_level: str
    seniority_order: int
    typical_appointments: str | None = None


class DirectorateRef(CamelModel):
    """A UPF directorate."""

    directorate_id: int
    name: str
    abbreviation: str | None = None
    is_training_authority: bool


class RegionRef(CamelModel):
    """A policing region."""

    region_id: int
    name: str
    headquarters: str | None = None


class StationRef(CamelModel):
    """A station, headquarters, or training institution."""

    station_id: int
    name: str
    region_id: int
    region_name: str
    district: str | None = None
    station_type: str
    is_active: bool


class SpecializationRef(CamelModel):
    """A training discipline. ``disciplineGroup`` is the subject grouping (ADR-0008)."""

    specialization_area_id: int
    name: str
    description: str | None = None
    discipline_group: str | None = None
    directorate_id: int | None = None
    is_active: bool


class CategoryRef(CamelModel):
    """A training delivery category — how a course is run, not what it is about."""

    category_id: int
    name: str
    description: str | None = None
    is_active: bool


class InstitutionRef(CamelModel):
    """A qualification-awarding institution."""

    institution_id: int
    name: str
    institution_type: str
    country: str


class LevelRef(CamelModel):
    """An ordered level with the score the algorithm assigns it.

    ``scoreValue`` is exposed so the frontend's Weight Studio can explain *why* a
    criterion scored as it did without hard-coding the table — the same reason the
    values live in the database at all (NFR-10).
    """

    level_id: int
    code: str
    name: str
    rank_order: int
    score_value: ScoreField


class ReferenceBundle(CamelModel):
    """Every lookup list in one response.

    The frontend needs six of these to render a single programme form. One round trip
    beats six, and the payload is a few kilobytes.
    """

    roles: list[RoleRef]
    ranks: list[RankRef]
    directorates: list[DirectorateRef]
    regions: list[RegionRef]
    stations: list[StationRef]
    specializations: list[SpecializationRef]
    categories: list[CategoryRef]
    institutions: list[InstitutionRef]
    qualification_levels: list[LevelRef]
    proficiency_levels: list[LevelRef]


__all__ = [
    "CategoryRef",
    "DirectorateRef",
    "InstitutionRef",
    "LevelRef",
    "RankRef",
    "ReferenceBundle",
    "RegionRef",
    "RoleRef",
    "SpecializationRef",
    "StationRef",
]
