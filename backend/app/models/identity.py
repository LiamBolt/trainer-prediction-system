"""Identity and access — users and refresh tokens (§5.2)."""

from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import CaseInsensitiveText, IpAddress
from app.models.enums import AccountStatus, check_in

if TYPE_CHECKING:
    from app.models.reference import PoliceRank, Role


class User(Base, TimestampMixin):
    """A system user account.

    Serves FR-01 (authentication) and FR-02 (role-based access control).

    ``username`` and ``email`` are ``CITEXT``, so ``G.Nabirye@upf.go.ug`` and
    ``g.nabirye@upf.go.ug`` cannot both be registered. That is the behaviour a user
    expects; plain ``VARCHAR`` silently permits both and produces two accounts for
    one person.

    ``failed_login_count`` and ``locked_until`` implement FR-01's three-strike,
    fifteen-minute lockout. They live on the user row rather than in a cache because a
    lockout must survive a process restart — an attacker who can crash the service
    must not thereby clear the counter.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(check_in("account_status", AccountStatus), name="account_status_valid"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_non_negative"),
        Index("ix_users_role_id", "role_id"),
        Index("ix_users_rank_id", "rank_id"),
        Index("ix_users_created_by_user_id", "created_by_user_id"),
        Index("ix_users_account_status", "account_status"),
        {"comment": "System user accounts. FR-01 authentication, FR-02 authorisation."},
    )

    user_id: Mapped[int] = primary_key()
    username: Mapped[str] = mapped_column(
        CaseInsensitiveText, nullable=False, unique=True, comment="Case-insensitive login name."
    )
    email: Mapped[str] = mapped_column(
        CaseInsensitiveText, nullable=False, unique=True, comment="Case-insensitive email address."
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Argon2id hash. Never logged, never returned by any endpoint.",
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="RESTRICT"), nullable=False
    )
    rank_id: Mapped[int | None] = mapped_column(
        ForeignKey("police_ranks.rank_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Police rank. NULL for any future civilian or service account.",
    )
    account_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AccountStatus.ACTIVE, server_default="ACTIVE"
    )
    failed_login_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Consecutive failed sign-ins. Reset to 0 on success (FR-01).",
    )
    locked_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Lockout expiry. NULL means not locked — the normal state (FR-01).",
    )
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful sign-in. NULL means the account has never been used.",
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True after an administrator resets the password.",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Administrator who created this account. NULL for the bootstrap administrator.",
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="raise_on_sql")
    rank: Mapped[PoliceRank | None] = relationship(lazy="raise_on_sql")
    created_by: Mapped[User | None] = relationship(remote_side="User.user_id", lazy="raise_on_sql")


class RefreshToken(Base, TimestampMixin):
    """A rotating refresh token, stored hashed.

    Only the **hash** is stored, never the token. A leaked database backup must not
    yield usable sessions — the same reasoning that applies to passwords applies here,
    because a refresh token *is* a credential.

    ``family_id`` groups the tokens produced by successive rotations of one login.
    When a token that has already been rotated is presented again, the only
    explanation is that it was stolen, so Phase 2 revokes the entire family rather
    than the single token.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_replaced_by_token_id", "replaced_by_token_id"),
        {"comment": "Hashed refresh tokens with rotation families for reuse detection."},
    )

    token_id: Mapped[int] = primary_key()
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="CASCADE: a deleted user's sessions are meaningless and must not outlive them.",
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA-256 of the token. The token itself is never stored.",
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Rotation family. Presenting a revoked token revokes every token sharing this id.",
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Revocation time. NULL means live — absence is the normal case.",
    )
    replaced_by_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.token_id", ondelete="SET NULL"),
        nullable=True,
        comment="The token issued when this one was rotated. Forms the rotation chain.",
    )
    created_by_ip: Mapped[str | None] = mapped_column(IpAddress, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(lazy="raise_on_sql")
