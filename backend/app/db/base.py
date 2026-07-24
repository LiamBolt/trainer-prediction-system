"""Declarative base, naming convention, and shared column mixins.

The naming convention is set on ``Base.metadata`` **before any model is defined**,
so every index, constraint, and key gets a deterministic name. Without it, Alembic
autogenerate emits phantom diffs forever: PostgreSQL invents names like
``trainers_user_id_key``, SQLAlchemy expects something else, and every
``--autogenerate`` run proposes dropping and recreating constraints that never
changed (§4).
"""

from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Deterministic constraint naming (§4). ``ck`` requires every ``CheckConstraint``
#: to be given an explicit ``name=``; an unnamed one raises at table-creation time,
#: which is the desired failure — silent auto-naming is what causes the drift.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every TPS model.

    The ORM is the single source of truth for the schema (D1); migrations are
    generated from these classes and then hand-reviewed.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def primary_key() -> Mapped[int]:
    """Return a ``BIGINT GENERATED ALWAYS AS IDENTITY`` primary key column.

    Integer, not UUID (D3). Every identifier in ``frontend/src/types/domain.ts`` is
    typed ``number``; a UUID would satisfy the compiler as a string and break the
    contract only at runtime. Human-facing identity is carried by registry numbers
    (§5.9), which is what belongs on a printed government record anyway.

    ``GENERATED ALWAYS`` rather than ``BY DEFAULT`` so an application cannot supply
    its own value and collide with the sequence.

    Returns:
        A mapped primary-key column.
    """
    return mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` to a table.

    Both are ``TIMESTAMPTZ`` (D5) defaulted server-side, so a row inserted by
    ``psql`` during an incident is stamped identically to one inserted by the ORM.

    ``updated_at`` is maintained by the shared ``set_updated_at()`` trigger installed
    in migration 0002 — **not** by SQLAlchemy's ``onupdate``. A trigger cannot be
    bypassed by a bulk ``UPDATE``, a raw ``text()`` statement, or a DBA at a psql
    prompt; ``onupdate`` can be bypassed by all three.
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Row creation time (UTC).",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Last modification time (UTC), maintained by the set_updated_at trigger.",
    )
