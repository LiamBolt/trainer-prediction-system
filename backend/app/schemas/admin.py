"""User administration, roles, and audit DTOs (FR-12, FR-13, §6.10, §6.11)."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CamelModel


class UserRead(CamelModel):
    """A user account. **Never carries a password field, in any form.**"""

    user_id: int
    username: str
    full_name: str
    email: str
    role: str = Field(description="Machine name, e.g. TRAINING_ADMINISTRATOR.")
    role_id: int
    role_display_name: str = ""
    rank: str | None = Field(default=None, description="Police rank code, where the user has one.")
    account_status: str
    must_change_password: bool
    last_login_at: datetime.datetime | None = None
    created_at: datetime.datetime
    trainer_id: int | None = Field(
        default=None, description="Set when the account is linked to a trainer profile."
    )


class UserCreateInput(CamelModel):
    """Creating a user (FR-12).

    No password field: the server generates a temporary one. Letting an administrator
    choose another person's initial password means it travels by whatever channel they
    use to pass it on and is very often reused.
    """

    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(min_length=3, max_length=150)
    email: EmailStr
    role: str = Field(description="One of the four role names.")
    rank_id: int | None = Field(default=None, gt=0)
    # The four fields below are required together when the role is TRAINER. The
    # `trainers` table declares all of them NOT NULL, so a partial trainer is not a
    # degraded record — it is an insert that fails.
    station_id: int | None = Field(
        default=None,
        gt=0,
        description="Required when the role is TRAINER — a trainer must have a posting.",
    )
    directorate_id: int | None = Field(
        default=None, gt=0, description="Required when the role is TRAINER."
    )
    force_number: str | None = Field(
        default=None, max_length=20, description="Required when the role is TRAINER."
    )
    contact_number: str | None = Field(
        default=None,
        max_length=24,
        description=(
            "Required when the role is TRAINER. A trainer who cannot be reached cannot "
            "be offered an assignment."
        ),
    )
    years_experience: int | None = Field(default=None, ge=0, le=60)


class UserCreated(CamelModel):
    """The response to creating a user.

    ``temporaryPassword`` is returned **once, here, in the body**. It is never logged,
    never stored in plaintext, never emailed by this system, and never retrievable
    again — a password that can be looked up later is not a password.
    """

    user: UserRead
    temporary_password: str = Field(
        description="Shown once. The user must change it at first sign-in."
    )
    message: str


class UserUpdateInput(CamelModel):
    """Editing a user (FR-12)."""

    full_name: str | None = Field(default=None, min_length=3, max_length=150)
    email: EmailStr | None = None
    role: str | None = None
    account_status: str | None = Field(default=None, description="ACTIVE or SUSPENDED.")
    rank_id: int | None = Field(default=None, gt=0)


class RoleRead(CamelModel):
    """A role with the permissions attached to it.

    ``permissions`` is served from here rather than hard-coded in the frontend so the
    Roles screen is data-driven — a table that has to be edited in two places to stay
    true will eventually be true in only one.
    """

    role_id: int
    name: str
    display_name: str
    description: str | None = None
    user_count: int = 0
    permissions: list[str] = Field(default_factory=list)


class AuditEntryRead(CamelModel):
    """One audit entry (FR-13). Read-only, by construction — see the router."""

    log_id: int
    actor_user_id: int | None = None
    actor_name: str | None = Field(
        default=None, description="Null for an unauthenticated action, e.g. a failed sign-in."
    )
    actor_role: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    before_json: dict[str, Any] | None = None
    after_json: dict[str, Any] | None = None
    detail: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime.datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def _stringify_ip(cls, value: object) -> str | None:
        """Render the stored address as text.

        The column uses PostgreSQL's ``INET`` type, so asyncpg hands back an
        :class:`ipaddress.IPv4Address` rather than a string. The wire contract is a
        string — `domain.ts` types it as one — and coercing here keeps that true for
        both IPv4 and IPv6 without the router knowing anything about it.

        Args:
            value: Whatever the driver returned.

        Returns:
            The address as text, or None.
        """
        if value is None:
            return None
        return str(value)


class PasswordReset(CamelModel):
    """The response to resetting a password."""

    temporary_password: str = Field(description="Shown once.")
    message: str
