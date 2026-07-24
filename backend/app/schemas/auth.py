"""Authentication request and response schemas (§6.1)."""

from __future__ import annotations

import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    """Credentials presented at sign-in."""

    username: str = Field(
        min_length=1,
        max_length=150,
        description="Username or email address. Case-insensitive.",
        examples=["admin.training"],
    )
    password: str = Field(
        min_length=1,
        max_length=256,
        description="The account password.",
        examples=["Tps@2026#Demo"],
    )


class RefreshRequest(CamelModel):
    """A refresh token presented for rotation."""

    refresh_token: str = Field(
        min_length=1, description="The refresh token issued at sign-in or last rotation."
    )


class ChangePasswordRequest(CamelModel):
    """A password change, authenticated by the current password."""

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(
        min_length=12,
        max_length=256,
        description="At least 12 characters. Length is the property that matters most.",
    )


class UserSummary(CamelModel):
    """The authenticated user, as returned by ``/auth/login`` and ``/auth/me``."""

    user_id: int
    username: str
    full_name: str
    email: str
    role_id: int
    role: str = Field(description="Role name, e.g. TRAINING_ADMINISTRATOR.")
    rank_code: str | None = Field(default=None, description="Police rank code, e.g. SSP.")
    account_status: str
    trainer_id: int | None = Field(
        default=None,
        description="Set only when the user is a Trainer. The frontend uses it to route.",
    )
    must_change_password: bool = False
    created_at: datetime.datetime
    last_login_at: datetime.datetime | None = None


class AuthSession(CamelModel):
    """A successful sign-in.

    ``token`` is named to match the frontend's existing ``AuthSession`` type rather
    than the more conventional ``accessToken`` — the frontend contract is binding.
    """

    token: str = Field(description="The bearer access token. Valid 15 minutes.")
    refresh_token: str = Field(description="Opaque refresh token. Valid 7 days, rotates on use.")
    expires_at: datetime.datetime = Field(description="Access token expiry, ISO-8601 with offset.")
    user: UserSummary


class LoginSuccess(CamelModel):
    """Discriminated login outcome: success."""

    outcome: str = "SUCCESS"
    session: AuthSession


class LoginInvalid(CamelModel):
    """Discriminated login outcome: bad credentials.

    ``attempts_remaining`` is returned only for accounts that exist **and** are not
    locked. It never reveals whether the username exists — an unknown username yields
    the same shape with the full allowance, so the response cannot be used to
    enumerate accounts.
    """

    outcome: str = "INVALID"
    attempts_remaining: int = Field(description="Attempts left before a 15-minute lockout.")


class LoginLocked(CamelModel):
    """Discriminated login outcome: account locked (FR-01)."""

    outcome: str = "LOCKED"
    unlock_at: datetime.datetime
    retry_after_seconds: int


class LoginDeactivated(CamelModel):
    """Discriminated login outcome: account deactivated (FR-12)."""

    outcome: str = "DEACTIVATED"
