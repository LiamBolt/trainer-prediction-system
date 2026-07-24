"""Trainer domain — trainers, their credentials, and declared absences (§5.3)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.models.enums import AvailabilityStatus, UnavailabilityCategory, check_in

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.reference import (
        Directorate,
        Institution,
        PoliceRank,
        ProficiencyLevel,
        QualificationLevel,
        SpecializationArea,
        Station,
    )


class Trainer(Base, TimestampMixin):
    """A police officer available to deliver training.

    Serves FR-03 (trainer profile management) and is the entity BR-03, BR-04, and the
    whole prediction engine operate on.

    ``user_id`` is ``UNIQUE`` and ``NOT NULL``: every trainer is a system user, and no
    user is two trainers. The FK is ``RESTRICT`` because deleting a user who has
    delivered training would orphan allocations and evaluations that form part of a
    decision record.

    ``searchable_name`` is denormalised from ``users.full_name``. §5.3 asks for a
    trigram index for fuzzy name search and requires the choice between joining and
    denormalising to be justified: a GIN trigram index cannot span a join, so
    ``ILIKE '%mugish%'`` against ``users`` would force a full scan of ``users``
    followed by a hash join on every keystroke of a type-ahead search. The column is
    maintained by Phase 2 on profile write and is the only intentional duplication in
    the trainer tables.
    """

    __tablename__ = "trainers"
    __table_args__ = (
        CheckConstraint(
            check_in("availability_status", AvailabilityStatus), name="availability_status_valid"
        ),
        CheckConstraint("years_experience BETWEEN 0 AND 50", name="years_experience_range"),
        CheckConstraint(
            "profile_completeness BETWEEN 0 AND 100", name="profile_completeness_range"
        ),
        Index("ix_trainers_station_id", "station_id"),
        Index("ix_trainers_directorate_id", "directorate_id"),
        Index("ix_trainers_rank_id", "rank_id"),
        # Partial index: every prediction query filters on availability first, and
        # roughly two thirds of trainers are AVAILABLE. Indexing only that subset
        # keeps the index small and the write cost proportionate.
        Index(
            "ix_trainers_available",
            "availability_status",
            postgresql_where=text("availability_status = 'AVAILABLE'"),
        ),
        # Fuzzy search over name and force number for the trainer directory.
        Index(
            "ix_trainers_searchable_name_trgm",
            "searchable_name",
            postgresql_using="gin",
            postgresql_ops={"searchable_name": "gin_trgm_ops"},
        ),
        Index(
            "ix_trainers_force_number_trgm",
            "force_number",
            postgresql_using="gin",
            postgresql_ops={"force_number": "gin_trgm_ops"},
        ),
        {"comment": "Police officers available to deliver training. FR-03."},
    )

    trainer_id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="The trainer's system account. One-to-one.",
    )
    force_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        comment="UPF force number, five digits, displayed as 'No. 41927'. The human identifier.",
    )
    rank_id: Mapped[int] = mapped_column(
        ForeignKey("police_ranks.rank_id", ondelete="RESTRICT"), nullable=False
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.station_id", ondelete="RESTRICT"), nullable=False
    )
    directorate_id: Mapped[int] = mapped_column(
        ForeignKey("directorates.directorate_id", ondelete="RESTRICT"), nullable=False
    )
    date_of_enlistment: Mapped[datetime.date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Enlistment date. NULL where the record predates digitisation.",
    )
    years_experience: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment=(
            "Years of service. Stored rather than derived from date_of_enlistment "
            "because that date is nullable for legacy records. The EXPERIENCE "
            "criterion saturates at 20 years (EXPERIENCE_CEILING_YEARS)."
        ),
    )
    availability_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AvailabilityStatus.AVAILABLE,
        server_default="AVAILABLE",
        comment="UNAVAILABLE is the BR-03 gate, applied before any scoring.",
    )
    contact_number: Mapped[str] = mapped_column(
        String(24), nullable=False, comment="Format '+256 772 419 273'."
    )
    bio: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Free-text biography. NULL means not yet supplied."
    )
    searchable_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Denormalised from users.full_name so the trigram index can be used. See class docstring.",
    )
    profile_completeness: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment=(
            "0-100. Contributes 35% of the confidence level shown beside every "
            "prediction. Derived from field presence (bio, contact, enlistment date, "
            ">=1 qualification, >=1 specialisation) and recomputed by Phase 2 on "
            "profile write. Stored, not computed on read, so a prediction's "
            "confidence can be reproduced exactly as it stood (conflict C6)."
        ),
    )

    user: Mapped[User] = relationship(lazy="raise_on_sql")
    rank: Mapped[PoliceRank] = relationship(lazy="raise_on_sql")
    station: Mapped[Station] = relationship(lazy="raise_on_sql")
    directorate: Mapped[Directorate] = relationship(lazy="raise_on_sql")
    qualifications: Mapped[list[TrainerQualification]] = relationship(
        back_populates="trainer", cascade="all, delete-orphan", lazy="raise_on_sql"
    )
    specializations: Mapped[list[TrainerSpecialization]] = relationship(
        back_populates="trainer", cascade="all, delete-orphan", lazy="raise_on_sql"
    )
    unavailability: Mapped[list[TrainerUnavailability]] = relationship(
        back_populates="trainer", cascade="all, delete-orphan", lazy="raise_on_sql"
    )


class TrainerQualification(Base, TimestampMixin):
    """An academic or professional qualification held by a trainer.

    ``CASCADE`` on delete: a qualification has no meaning without its trainer. This is
    the narrow case where cascade is correct — contrast with allocations and
    evaluations, which form part of a decision record and outlive everything.
    """

    __tablename__ = "trainer_qualifications"
    __table_args__ = (
        CheckConstraint(
            "year_obtained BETWEEN 1960 AND EXTRACT(YEAR FROM CURRENT_DATE)::smallint",
            name="year_obtained_range",
        ),
        Index("ix_trainer_qualifications_trainer_id", "trainer_id"),
        Index("ix_trainer_qualifications_level_id", "level_id"),
        Index("ix_trainer_qualifications_institution_id", "institution_id"),
        {"comment": "Qualifications held by a trainer. FR-03."},
    )

    qualification_id: Mapped[int] = primary_key()
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="CASCADE"), nullable=False
    )
    qualification_name: Mapped[str] = mapped_column(
        String(160), nullable=False, comment="e.g. 'MSc, Criminal Justice'."
    )
    level_id: Mapped[int] = mapped_column(
        ForeignKey("qualification_levels.level_id", ondelete="RESTRICT"), nullable=False
    )
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.institution_id", ondelete="RESTRICT"), nullable=False
    )
    year_obtained: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    trainer: Mapped[Trainer] = relationship(back_populates="qualifications", lazy="raise_on_sql")
    level: Mapped[QualificationLevel] = relationship(lazy="raise_on_sql")
    institution: Mapped[Institution] = relationship(lazy="raise_on_sql")


class TrainerSpecialization(Base, TimestampMixin):
    """A discipline a trainer is proficient in, at a stated level.

    The ``UNIQUE(trainer_id, specialization_area_id)`` constraint encodes a real rule:
    a trainer holds exactly one proficiency per area. Without it, a profile edit that
    inserts instead of updating would leave two rows and the scoring engine would pick
    whichever the planner returned first.
    """

    __tablename__ = "trainer_specializations"
    __table_args__ = (
        UniqueConstraint(
            "trainer_id", "specialization_area_id", name="uq_trainer_specializations_trainer_area"
        ),
        CheckConstraint(
            "years_in_area IS NULL OR years_in_area BETWEEN 0 AND 50", name="years_in_area_range"
        ),
        Index("ix_trainer_specializations_trainer_id", "trainer_id"),
        # BR-04's filter rides this index: "who holds the required specialisation, and
        # at what proficiency?" is the first question every prediction run asks.
        Index(
            "ix_trainer_specializations_area_proficiency",
            "specialization_area_id",
            "proficiency_level_id",
        ),
        {"comment": "Trainer proficiency per discipline. BR-04 matches on this."},
    )

    specialization_id: Mapped[int] = primary_key()
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="CASCADE"), nullable=False
    )
    specialization_area_id: Mapped[int] = mapped_column(
        ForeignKey("specialization_areas.specialization_area_id", ondelete="RESTRICT"),
        nullable=False,
    )
    proficiency_level_id: Mapped[int] = mapped_column(
        ForeignKey("proficiency_levels.level_id", ondelete="RESTRICT"), nullable=False
    )
    years_in_area: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="Years worked in this discipline. NULL means not recorded.",
    )

    trainer: Mapped[Trainer] = relationship(back_populates="specializations", lazy="raise_on_sql")
    area: Mapped[SpecializationArea] = relationship(lazy="raise_on_sql")
    proficiency: Mapped[ProficiencyLevel] = relationship(lazy="raise_on_sql")


class TrainerUnavailability(Base, TimestampMixin):
    """A declared absence window — leave, court, deployment, study, or medical.

    This table is what lets a decline be *corroborated* rather than merely asserted.
    When a trainer declines an assignment citing court testimony, a matching row here
    turns a free-text excuse into an auditable fact (§7.4, fixture 3).

    An ``EXCLUDE USING gist`` constraint prevents one trainer's windows from
    overlapping. A trainer cannot simultaneously be on leave and in court, and an
    overlap would double-count against BR-03. ``btree_gist`` supplies the integer
    equality operator that lets ``trainer_id`` participate in a GiST exclusion
    alongside the date range. The constraint is raw DDL in migration 0002, because
    Alembic autogenerate does not emit ``EXCLUDE`` constraints at all — it would
    silently produce a schema without it.
    """

    __tablename__ = "trainer_unavailability"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="end_date_after_start_date"),
        CheckConstraint(check_in("category", UnavailabilityCategory), name="category_valid"),
        Index("ix_trainer_unavailability_trainer_dates", "trainer_id", "start_date", "end_date"),
        Index("ix_trainer_unavailability_recorded_by_user_id", "recorded_by_user_id"),
        {"comment": "Declared absence windows. Corroborates BR-03 exclusions and declines."},
    )

    unavailability_id: Mapped[int] = primary_key()
    trainer_id: Mapped[int] = mapped_column(
        ForeignKey("trainers.trainer_id", ondelete="CASCADE"), nullable=False
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="Inclusive last day of absence."
    )
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    recorded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Who recorded it. NULL when the trainer declared it themselves.",
    )

    trainer: Mapped[Trainer] = relationship(back_populates="unavailability", lazy="raise_on_sql")
