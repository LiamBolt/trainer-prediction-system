"""Scoring policy — the retunable weighting model (§5.5, NFR-10)."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import Weight
from app.models.enums import CriterionKey, check_in

if TYPE_CHECKING:
    from app.models.identity import User


class ScoringPolicy(Base, TimestampMixin):
    """A versioned set of scoring weights.

    Serves NFR-10 (a modular, retunable prediction engine). A policy is versioned and
    superseded rather than edited, so a prediction generated last quarter can still be
    explained by the policy that produced it.

    Exactly one policy may be active at a time. That is enforced by a **partial unique
    index** on ``is_active WHERE is_active`` rather than by application code, because
    it is a business invariant and the database is the only layer no bug can bypass.
    A plain unique index would permit only one *inactive* policy, which is the
    opposite of what is wanted.
    """

    __tablename__ = "scoring_policies"
    __table_args__ = (
        Index(
            "uq_scoring_policies_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index("ix_scoring_policies_created_by_user_id", "created_by_user_id"),
        {"comment": "Versioned scoring weight sets. Exactly one is active (NFR-10)."},
    )

    policy_id: Mapped[int] = primary_key()
    version: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, unique=True, comment="Monotonic policy version, from 1."
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Exactly one row may be true, enforced by a partial unique index.",
    )
    effective_from: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Why this policy was adopted. NULL for the initial policy."
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL for the policy seeded at go-live, which no user created.",
    )

    weights: Mapped[list[ScoringPolicyWeight]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", lazy="raise_on_sql"
    )
    created_by: Mapped[User | None] = relationship(lazy="raise_on_sql")


class ScoringPolicyWeight(Base, TimestampMixin):
    """The weight assigned to one criterion under one policy.

    **Rows, not columns** (D8). Adding a sixth scoring criterion must not require a
    schema migration — that is what makes NFR-10's "modular, retunable prediction
    engine" real rather than aspirational. As columns, every criterion change would be
    an ``ALTER TABLE`` plus a deployment; as rows it is an ``INSERT``.

    ``description`` is the plain-English explanation the frontend's Weight Studio
    displays beside each slider. It lives here, not in the frontend, so that an
    administrator who retunes a weight can also correct the sentence that explains it
    without a release.

    The weights of a policy must sum to 100. That cannot be expressed as a row-level
    ``CHECK``, since a check sees only its own row. It is enforced by a **deferred
    constraint trigger** installed in migration 0002, which fires at ``COMMIT`` — by
    which point all five rows exist. See ADR and §5.5.
    """

    __tablename__ = "scoring_policy_weights"
    __table_args__ = (
        UniqueConstraint(
            "policy_id", "criterion_key", name="uq_scoring_policy_weights_policy_criterion"
        ),
        CheckConstraint(check_in("criterion_key", CriterionKey), name="criterion_key_valid"),
        CheckConstraint("weight >= 0 AND weight <= 100", name="weight_range"),
        Index("ix_scoring_policy_weights_policy_id", "policy_id"),
        {
            "comment": "Per-criterion weights. Rows not columns, so criteria change without migration."
        },
    )

    weight_id: Mapped[int] = primary_key()
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_policies.policy_id", ondelete="CASCADE"),
        nullable=False,
        comment="CASCADE: a weight has no meaning without its policy.",
    )
    criterion_key: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="One of the five CriterionKey values."
    )
    display_label: Mapped[str] = mapped_column(
        String(60), nullable=False, comment="e.g. 'Specialisation match'."
    )
    weight: Mapped[Decimal] = mapped_column(
        Weight, nullable=False, comment="Points available for this criterion. All five sum to 100."
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Plain-English explanation shown in the Weight Studio."
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="Display order, heaviest criterion first."
    )

    policy: Mapped[ScoringPolicy] = relationship(back_populates="weights", lazy="raise_on_sql")
