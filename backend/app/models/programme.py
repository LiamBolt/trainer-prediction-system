"""Training programme domain (§5.4)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.models.enums import ProgrammeStatus, check_in

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.reference import (
        QualificationLevel,
        SpecializationArea,
        Station,
        TrainingCategory,
    )


class TrainingProgramme(Base, TimestampMixin):
    """A training course requiring one or more trainers.

    Serves FR-04 (create a training request) and FR-05 (define its requirements).

    ``required_specialization_area_id`` is deliberately **nullable**. That nullability
    is what makes the ``DRAFT`` → ``REQUIREMENTS_SET`` transition mean something: a
    programme in ``DRAFT`` genuinely has no requirement recorded, and a prediction run
    against it is impossible rather than merely discouraged. Encoding the distinction
    as a status flag alone would let a bug run a prediction against no requirement and
    rank the entire force.

    ``requirements_changed_since_prediction`` drives FR-05's re-rank banner. It is a
    stored flag rather than a timestamp comparison because "changed" is a business
    event — an officer editing a title has not invalidated a prediction, but an
    officer raising the minimum experience has.
    """

    __tablename__ = "training_programmes"
    __table_args__ = (
        CheckConstraint(check_in("status", ProgrammeStatus), name="status_valid"),
        CheckConstraint("end_date >= start_date", name="end_date_after_start_date"),
        CheckConstraint("minimum_experience BETWEEN 0 AND 50", name="minimum_experience_range"),
        CheckConstraint(
            "expected_participants IS NULL OR expected_participants > 0",
            name="expected_participants_positive",
        ),
        # A programme past DRAFT must carry a requirement — the invariant the
        # nullable FK above exists to express. Enforced here so no code path can
        # advance a programme without defining what it needs.
        CheckConstraint(
            "status = 'DRAFT' OR status = 'CANCELLED' "
            "OR required_specialization_area_id IS NOT NULL",
            name="requirements_set_beyond_draft",
        ),
        Index("ix_training_programmes_status", "status"),
        Index("ix_training_programmes_category_id", "category_id"),
        Index(
            "ix_training_programmes_required_specialization_area_id",
            "required_specialization_area_id",
        ),
        Index("ix_training_programmes_created_by_user_id", "created_by_user_id"),
        Index("ix_training_programmes_station_id", "station_id"),
        Index(
            "ix_training_programmes_minimum_qualification_level_id",
            "minimum_qualification_level_id",
        ),
        Index("ix_training_programmes_dates", "start_date", "end_date"),
        Index(
            "ix_training_programmes_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        {"comment": "Training courses and their requirements. FR-04, FR-05."},
    )

    programme_id: Mapped[int] = primary_key()
    registry_number: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        comment="Human-facing identifier, e.g. 'TPS/REQ/2026/0132'. From next_registry_number('REQ').",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("training_categories.category_id", ondelete="RESTRICT"), nullable=False
    )
    required_specialization_area_id: Mapped[int | None] = mapped_column(
        ForeignKey("specialization_areas.specialization_area_id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL until FR-05 requirements are defined. See class docstring.",
    )
    minimum_experience: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Minimum years of service. 0 means no bar. FR-05 gate.",
    )
    minimum_qualification_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("qualification_levels.level_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Minimum qualification. NULL means none required — a meaningful absence.",
    )
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.station_id", ondelete="RESTRICT"),
        nullable=False,
        comment="Venue where the course is delivered.",
    )
    expected_participants: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="Planned intake size. NULL when not yet decided."
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ProgrammeStatus.DRAFT, server_default="DRAFT"
    )
    requirements_set_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When FR-05 requirements were defined. NULL while still DRAFT.",
    )
    requirements_changed_since_prediction: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Drives the FR-05 re-rank banner: the ranking on screen may be stale.",
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )

    category: Mapped[TrainingCategory] = relationship(lazy="raise_on_sql")
    required_specialization_area: Mapped[SpecializationArea | None] = relationship(
        lazy="raise_on_sql"
    )
    minimum_qualification_level: Mapped[QualificationLevel | None] = relationship(
        lazy="raise_on_sql"
    )
    station: Mapped[Station] = relationship(lazy="raise_on_sql")
    created_by: Mapped[User] = relationship(lazy="raise_on_sql")
