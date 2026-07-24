"""Reference tables — seeded once, rarely changed (§5.1).

Ten lookup tables carrying the organisational vocabulary of the Uganda Police Force:
its rank ladder, directorates, policing regions, stations, training institutions, and
the controlled vocabularies the business rules match against.

Two of these tables carry **score values** (``qualification_levels``,
``proficiency_levels``). Those values are data, not code, because NFR-10 requires the
scoring model to be retunable without redeploying anything. Hard-coding
``{"EXPERT": 100}`` in Python makes a policy change a code change, a migration, a
rebuild, and a deployment. As a row it is an ``UPDATE``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import Score
from app.models.enums import (
    InstitutionType,
    ManagementLevel,
    RoleName,
    StationType,
    check_in,
)

if TYPE_CHECKING:
    from app.models.identity import User


class Role(Base, TimestampMixin):
    """A system role — one of the four SRS actors.

    Serves FR-02 (role-based access control). Roles are a table rather than an enum
    because ``users.role_id`` is a foreign key, which makes "every user has a valid
    role" a database guarantee rather than an application convention.
    """

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(check_in("name", RoleName), name="name_valid"),
        {"comment": "The four SRS actor roles. Seeded; not user-editable."},
    )

    role_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        unique=True,
        comment="Machine name, e.g. TRAINING_ADMINISTRATOR. Matches domain.ts:RoleName.",
    )
    display_name: Mapped[str] = mapped_column(
        String(80), nullable=False, comment="Human-facing label, e.g. 'Training Administrator'."
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="What this role may do, in plain English."
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="True for the four built-in roles, which must not be deleted.",
    )

    users: Mapped[list[User]] = relationship(back_populates="role", lazy="raise_on_sql")
    """Users holding this role.

    ``lazy="raise_on_sql"`` throughout the models: in async SQLAlchemy an
    un-eager-loaded relationship raises ``MissingGreenlet`` at an arbitrary point far
    from the cause. Raising at access time instead turns every accidental N+1 into a
    loud, local failure during development (knowledge base §4.1).
    """


class PoliceRank(Base, TimestampMixin):
    """A rank on the UPF ladder, ordered junior to senior.

    ``seniority_order`` is the orderable key. Rank codes are not orderable as text —
    'ACP' sorts before 'PC' alphabetically but outranks it by nine steps — so any
    query that means "at least an Inspector" must compare ``seniority_order``.
    """

    __tablename__ = "police_ranks"
    __table_args__ = (
        CheckConstraint(
            check_in("management_level", ManagementLevel), name="management_level_valid"
        ),
        CheckConstraint("seniority_order > 0", name="seniority_order_positive"),
        {"comment": "The UPF rank ladder, seeded from the official structure."},
    )

    rank_id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(
        String(8), nullable=False, unique=True, comment="Short code, e.g. 'ASP'."
    )
    full_name: Mapped[str] = mapped_column(
        String(80), nullable=False, comment="e.g. 'Assistant Superintendent of Police'."
    )
    management_level: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="Band: STRATEGIC, SENIOR, MIDDLE, or JUNIOR.",
    )
    seniority_order: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        unique=True,
        comment="1 = most junior (SPC), 15 = most senior (IGP). The orderable key.",
    )
    typical_appointments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Posts the UPF attaches to this rank. Guides plausible seed data (§7.2).",
    )


class Directorate(Base, TimestampMixin):
    """A UPF directorate.

    ``is_training_authority`` marks the Directorate of Human Resource Development,
    which owns training in the UPF and is the organisational home of TPS.
    """

    __tablename__ = "directorates"
    __table_args__ = ({"comment": "The 17 UPF directorates."},)

    directorate_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    abbreviation: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="e.g. 'CID'. NULL where the UPF uses no abbreviation."
    )
    is_training_authority: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True only for Human Resource Development — the directorate that owns training.",
    )


class Region(Base, TimestampMixin):
    """A UPF policing region."""

    __tablename__ = "regions"
    __table_args__ = ({"comment": "UPF policing regions."},)

    region_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    headquarters: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="Town hosting the regional headquarters."
    )

    stations: Mapped[list[Station]] = relationship(back_populates="region", lazy="raise_on_sql")


class Station(Base, TimestampMixin):
    """A station, division, headquarters, training school, or specialised unit.

    Serves as both a trainer's posting and a programme's venue, which is why
    ``station_type`` matters: a course is held at a ``TRAINING_INSTITUTION``, while a
    trainer is posted to a ``STATION``.
    """

    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("name", "region_id", name="uq_stations_name_region_id"),
        CheckConstraint(check_in("station_type", StationType), name="station_type_valid"),
        Index("ix_stations_region_id", "region_id"),
        Index("ix_stations_station_type", "station_type"),
        {"comment": "UPF establishments: stations, divisions, HQs, and training schools."},
    )

    station_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.region_id", ondelete="RESTRICT"), nullable=False
    )
    district: Mapped[str | None] = mapped_column(
        String(80), nullable=True, comment="Administrative district. NULL for national HQ units."
    )
    station_type: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    region: Mapped[Region] = relationship(back_populates="stations", lazy="raise_on_sql")


class SpecializationArea(Base, TimestampMixin):
    """A discipline a trainer can specialise in — the vocabulary BR-04 matches against.

    A table rather than free text because BR-04 excludes a trainer who lacks the
    required specialisation. If specialisation were a string, that rule would degrade
    into string comparison and fail silently on "Cybercrime Investigations" versus
    "Cybercrime Investigation". A foreign key makes the business rule structurally
    enforceable.

    ``discipline_group`` exists because §5.1's ``training_categories`` is a
    *delivery-mode* taxonomy (Refresher, Induction, Pre-Deployment) while the scoring
    engine needs a *subject* taxonomy (Investigations, Forensics, Traffic). Two rules
    depend on the subject grouping: the SPECIALIZATION breadth bonus, and the
    PERFORMANCE relevance test that decides whether a past evaluation counts toward
    this programme. See ADR-0008.
    """

    __tablename__ = "specialization_areas"
    __table_args__ = (
        Index("ix_specialization_areas_directorate_id", "directorate_id"),
        Index("ix_specialization_areas_discipline_group", "discipline_group"),
        {"comment": "Controlled vocabulary of training disciplines. BR-04 matches on this."},
    )

    specialization_area_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    directorate_id: Mapped[int | None] = mapped_column(
        ForeignKey("directorates.directorate_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Directorate owning this discipline. NULL where ownership is shared.",
    )
    discipline_group: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        comment=(
            "Subject grouping, e.g. 'Investigations'. Drives the SPECIALIZATION breadth "
            "bonus and the PERFORMANCE relevance test (ADR-0008). NULL means ungrouped, "
            "so neither rule fires — a safe default, not a silent failure."
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    directorate: Mapped[Directorate | None] = relationship(lazy="raise_on_sql")


class TrainingCategory(Base, TimestampMixin):
    """A category of training delivery — how a course is run, not what it is about.

    Distinct from :attr:`SpecializationArea.discipline_group`, which carries subject.
    A "Refresher" (category) course may be about "Cybercrime Investigation"
    (specialisation, in the "Investigations" discipline group).
    """

    __tablename__ = "training_categories"
    __table_args__ = ({"comment": "Delivery-mode taxonomy: Refresher, Induction, and so on."},)

    category_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class Institution(Base, TimestampMixin):
    """An institution where a qualification was obtained.

    ``institution_type = 'POLICE'`` is load-bearing: it drives the QUALIFICATION
    criterion's +8 bonus for police-college training. Expressing that as a column
    rather than a hard-coded name list (as the frontend does) means a newly added
    police school automatically qualifies.
    """

    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint(
            check_in("institution_type", InstitutionType), name="institution_type_valid"
        ),
        Index("ix_institutions_institution_type", "institution_type"),
        {"comment": "Awarding institutions for trainer qualifications."},
    )

    institution_id: Mapped[int] = primary_key()
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    institution_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        comment="POLICE, UNIVERSITY, PROFESSIONAL, or INTERNATIONAL. POLICE earns a scoring bonus.",
    )
    country: Mapped[str] = mapped_column(
        String(60), nullable=False, default="Uganda", server_default="Uganda"
    )


class QualificationLevel(Base, TimestampMixin):
    """An academic qualification level, ordered, with the score the algorithm assigns.

    ``rank_order`` gives the comparison FR-05's minimum-qualification gate needs;
    ``score_value`` is what the QUALIFICATION criterion normalises from. Both are data
    so that policy can be retuned with an ``UPDATE`` (NFR-10).
    """

    __tablename__ = "qualification_levels"
    __table_args__ = (
        CheckConstraint("score_value >= 0 AND score_value <= 100", name="score_value_range"),
        CheckConstraint("rank_order > 0", name="rank_order_positive"),
        {"comment": "Ordered qualification levels with their scoring values (NFR-10)."},
    )

    level_id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(
        String(24), nullable=False, unique=True, comment="e.g. 'MASTERS'. Matches domain.ts."
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    rank_order: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        unique=True,
        comment="1 = Certificate, 6 = Doctorate. Compared by FR-05's minimum-qualification gate.",
    )
    score_value: Mapped[Decimal] = mapped_column(
        Score, nullable=False, comment="0-100 score fed to the QUALIFICATION criterion."
    )


class ProficiencyLevel(Base, TimestampMixin):
    """A proficiency level within a specialisation, ordered, with its score."""

    __tablename__ = "proficiency_levels"
    __table_args__ = (
        CheckConstraint("score_value >= 0 AND score_value <= 100", name="score_value_range"),
        CheckConstraint("rank_order > 0", name="rank_order_positive"),
        {"comment": "Ordered proficiency levels with their scoring values (NFR-10)."},
    )

    level_id: Mapped[int] = primary_key()
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    rank_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, unique=True, comment="1 = Basic, 4 = Expert."
    )
    score_value: Mapped[Decimal] = mapped_column(
        Score, nullable=False, comment="0-100 score fed to the SPECIALIZATION criterion."
    )


__all__ = [
    "Directorate",
    "Institution",
    "PoliceRank",
    "ProficiencyLevel",
    "QualificationLevel",
    "Region",
    "Role",
    "SpecializationArea",
    "Station",
    "TrainingCategory",
]
