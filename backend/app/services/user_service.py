"""User administration (FR-12). Imports no `fastapi` (B7).

Three rules shape this module, all of them about what the system refuses to do.

**A Trainer user and a trainer profile are created together or not at all.** A user with
the TRAINER role and no `trainers` row cannot see their assignments, cannot be ranked,
and cannot be evaluated — a broken state that looks fine on the user-administration
screen. One transaction makes it impossible rather than merely unlikely.

**The temporary password is returned once and never again.** It is generated here,
hashed immediately, and the plaintext exists only in the response body. It is not
logged, not stored, and not retrievable. A password an administrator can look up later
is not a password.

**The last active System Administrator cannot be deactivated.** Locking every
administrator out of a government system is a recoverable mistake only by someone with
database access, which is precisely the access this role exists to avoid needing.
"""

from __future__ import annotations

import secrets
import string
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.enums import AccountStatus, AuditAction, AvailabilityStatus, RoleName
from app.models.identity import RefreshToken, User
from app.models.reference import PoliceRank, Role
from app.models.trainer import Trainer
from app.schemas.admin import RoleRead, UserCreateInput, UserRead, UserUpdateInput
from app.services.audit_service import AuditService

#: Password alphabet for generated temporaries. Ambiguous glyphs are left out — an
#: administrator reads these aloud or writes them on paper, and `l`/`1`/`I` and
#: `O`/`0` produce support calls, not security.
_ALPHABET = (
    "".join(c for c in string.ascii_uppercase if c not in "OI")
    + "".join(c for c in string.ascii_lowercase if c not in "l")
    + "".join(c for c in string.digits if c not in "01")
    + "!@#$%&*?"
)

TEMPORARY_PASSWORD_LENGTH = 14

#: What each role may do, in plain English, served to the Roles screen so the frontend
#: does not keep a second copy that can disagree with this one.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleName.TRAINING_ADMINISTRATOR: [
        "Approve trainer allocations (BR-02)",
        "Generate and simulate predictions",
        "Record performance evaluations",
        "Promote the next candidate after a decline",
        "Mark training as conducted, and withdraw offers",
        "View all trainers, programmes, allocations, and reports",
    ],
    RoleName.TRAINING_OFFICER: [
        "Raise training requests and define their requirements",
        "Generate predictions and preview eligibility",
        "View all trainers, programmes, allocations, and evaluations",
        "May not approve an allocation — BR-02 reserves that to the Administrator",
    ],
    RoleName.TRAINER: [
        "Maintain their own profile, qualifications, and specialisations",
        "Declare unavailability windows",
        "Accept or decline their own assignments (FR-09)",
        "View their own performance history and the reason they were selected",
    ],
    RoleName.SYSTEM_ADMINISTRATOR: [
        "Create, edit, deactivate, and reset users",
        "Set the scoring policy weights (NFR-10)",
        "Read and export the audit log (FR-13)",
        "View system health and security figures",
    ],
}


def generate_temporary_password(length: int = TEMPORARY_PASSWORD_LENGTH) -> str:
    """Generate a temporary password.

    Uses :mod:`secrets`, not :mod:`random`. The seed data is deliberately reproducible
    from a fixed seed; a credential must be exactly the opposite.

    Args:
        length: How many characters.

    Returns:
        A random password.
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class UserService:
    """Creates and administers user accounts.

    Args:
        session: The request's session.
        audit: Audit service sharing the transaction (B8).
        clock: Injected clock.
    """

    def __init__(self, session: AsyncSession, audit: AuditService, clock: Clock) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock

    def list_query(self) -> Select[Any]:
        """Build the base projection for the user list."""
        return (
            select(
                User.user_id,
                User.username,
                User.full_name,
                User.email,
                Role.name.label("role"),
                User.role_id,
                Role.display_name.label("role_display_name"),
                PoliceRank.code.label("rank"),
                User.account_status,
                User.must_change_password,
                User.last_login_at,
                User.created_at,
                Trainer.trainer_id,
            )
            .join(Role, Role.role_id == User.role_id)
            .outerjoin(PoliceRank, PoliceRank.rank_id == User.rank_id)
            .outerjoin(Trainer, Trainer.user_id == User.user_id)
        )

    @staticmethod
    def apply_filters(
        query: Select[Any],
        *,
        search: str | None = None,
        role: str | None = None,
        account_status: str | None = None,
    ) -> Select[Any]:
        """Apply list filters.

        Args:
            query: The base query.
            search: Free text over username, full name, and email.
            role: Role name.
            account_status: ACTIVE, SUSPENDED, or DEACTIVATED.

        Returns:
            The filtered query.
        """
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.username.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        if role:
            query = query.where(Role.name == role)
        if account_status:
            query = query.where(User.account_status == account_status)
        return query

    async def count(self, query: Select[Any]) -> int:
        """Count rows a filtered query would return."""
        result = await self._session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one())

    async def get(self, user_id: int) -> UserRead:
        """Return one user.

        Args:
            user_id: Primary key.

        Returns:
            The user.

        Raises:
            NotFoundError: If it does not exist.
        """
        result = await self._session.execute(self.list_query().where(User.user_id == user_id))
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("That user account could not be found.")
        return UserRead.model_validate(row)

    async def create(self, payload: UserCreateInput, actor_user_id: int) -> tuple[UserRead, str]:
        """Create a user, and a trainer profile if the role requires one (FR-12).

        Args:
            payload: The new account's particulars.
            actor_user_id: The creating System Administrator.

        Returns:
            The created user and the temporary password, which is shown once.

        Raises:
            ConflictError: If the username or email is taken.
            NotFoundError: If the role does not exist.
            ValidationError: If a Trainer is created without a posting or force number.
        """
        await self._assert_unique(payload.username, payload.email)

        role = await self._role_by_name(payload.role)
        is_trainer = role.name == RoleName.TRAINER
        if is_trainer:
            self._assert_trainer_fields(payload)

        temporary = generate_temporary_password()
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(temporary),
            full_name=payload.full_name,
            role_id=role.role_id,
            rank_id=payload.rank_id,
            account_status=AccountStatus.ACTIVE.value,
            failed_login_count=0,
            must_change_password=True,
            created_by_user_id=actor_user_id,
        )
        self._session.add(user)
        await self._session.flush()

        if is_trainer:
            # Same transaction. A TRAINER user with no trainers row cannot see their
            # assignments and cannot be ranked — a state that must be impossible, not
            # merely unlikely.
            trainer = Trainer(
                user_id=user.user_id,
                force_number=payload.force_number,
                rank_id=payload.rank_id,
                station_id=payload.station_id,
                directorate_id=payload.directorate_id,
                contact_number=payload.contact_number,
                years_experience=payload.years_experience or 0,
                availability_status=AvailabilityStatus.AVAILABLE.value,
                # Denormalised from users.full_name so the trigram index can span it —
                # a GIN index cannot cross a join, and the trainer directory searches
                # on every keystroke. Maintained on write; see the model docstring.
                searchable_name=payload.full_name,
                profile_completeness=0,
            )
            self._session.add(trainer)
            await self._session.flush()

        await self._audit.record(
            AuditAction.USER_CREATED,
            entity_type="USER",
            entity_id=user.user_id,
            # The temporary password is not passed here in any form. The audit
            # scrubber would redact a field named `temporary_password`, but the
            # safest redaction is the value never reaching the call.
            after={
                "username": payload.username,
                "role": role.name,
                "full_name": payload.full_name,
                "trainer_profile_created": is_trainer,
            },
            detail=f"Created {role.display_name} account '{payload.username}'.",
        )
        return await self.get(user.user_id), temporary

    async def update(
        self, user_id: int, payload: UserUpdateInput, actor_user_id: int
    ) -> tuple[UserRead, str | None]:
        """Edit a user (FR-12).

        A role change takes effect at the user's **next sign-in**, because the role is
        carried in the access token. Rather than leave that as a surprise, the caller
        gets a sentence saying so, and every refresh family is revoked so the change
        lands within the access token's lifetime rather than at its leisure.

        Args:
            user_id: Primary key.
            payload: The fields to change.
            actor_user_id: The acting System Administrator.

        Returns:
            The updated user, and a note about the role change if there was one.

        Raises:
            NotFoundError: If the user or role does not exist.
            ConflictError: If the email is taken, or the last administrator is suspended.
        """
        user = await self._load(user_id)
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        role_note: str | None = None

        if payload.email and payload.email != user.email:
            await self._assert_unique(None, payload.email, exclude_user_id=user_id)
            before["email"] = user.email
            after["email"] = payload.email
            user.email = payload.email

        for field in ("full_name", "rank_id"):
            value = getattr(payload, field)
            if value is not None and value != getattr(user, field):
                before[field] = getattr(user, field)
                after[field] = value
                setattr(user, field, value)

        if payload.role:
            role = await self._role_by_name(payload.role)
            if role.role_id != user.role_id:
                previous = await self._session.get(Role, user.role_id)
                before["role"] = previous.name if previous else None
                after["role"] = role.name
                user.role_id = role.role_id
                await self._revoke_sessions(user_id)
                role_note = (
                    f"The role is now {role.display_name}. Because the role travels in "
                    "the access token, it takes effect at their next sign-in — their "
                    "current sessions have been revoked so that happens immediately."
                )

        if payload.account_status and payload.account_status != user.account_status:
            if payload.account_status == AccountStatus.DEACTIVATED:
                raise ConflictError(
                    "Use the deactivate endpoint rather than editing the status — it "
                    "also revokes the user's sessions, which this does not."
                )
            if payload.account_status == AccountStatus.SUSPENDED:
                await self._assert_not_last_administrator(user, "suspended")
            before["account_status"] = user.account_status
            after["account_status"] = payload.account_status
            user.account_status = payload.account_status
            if payload.account_status == AccountStatus.SUSPENDED:
                await self._revoke_sessions(user_id)

        await self._session.flush()

        if after:
            await self._audit.record(
                AuditAction.ROLE_CHANGED if "role" in after else AuditAction.USER_MODIFIED,
                entity_type="USER",
                entity_id=user_id,
                before=before,
                after=after,
                detail=f"Modified account '{user.username}': {', '.join(sorted(after))}.",
            )
        _ = actor_user_id
        return await self.get(user_id), role_note

    async def deactivate(self, user_id: int, actor_user_id: int) -> UserRead:
        """Deactivate a user and revoke every session immediately (§6.10).

        A deactivated user cannot sign in even with the correct password, and cannot
        continue on an access token issued a minute ago — ``get_current_user`` re-reads
        the account status from the database on every request precisely so that
        revocation is immediate rather than eventual.

        Args:
            user_id: Primary key.
            actor_user_id: The acting System Administrator.

        Returns:
            The deactivated user.

        Raises:
            ConflictError: If this is the last active System Administrator.
        """
        user = await self._load(user_id)
        if user.user_id == actor_user_id:
            raise ConflictError(
                "You cannot deactivate your own account. Ask another System "
                "Administrator to do it."
            )
        if user.account_status == AccountStatus.DEACTIVATED:
            raise ConflictError("That account is already deactivated.")

        await self._assert_not_last_administrator(user, "deactivated")

        user.account_status = AccountStatus.DEACTIVATED.value
        revoked = await self._revoke_sessions(user_id)
        await self._session.flush()

        await self._audit.record(
            AuditAction.USER_DEACTIVATED,
            entity_type="USER",
            entity_id=user_id,
            before={"account_status": AccountStatus.ACTIVE.value},
            after={"account_status": AccountStatus.DEACTIVATED.value},
            detail=(
                f"Deactivated account '{user.username}'; {revoked} session"
                f"{'s' if revoked != 1 else ''} revoked."
            ),
        )
        return await self.get(user_id)

    async def reset_password(self, user_id: int, actor_user_id: int) -> str:
        """Issue a new temporary password and revoke every session (§6.10).

        Args:
            user_id: Primary key.
            actor_user_id: The acting System Administrator.

        Returns:
            The temporary password, shown once.
        """
        user = await self._load(user_id)
        temporary = generate_temporary_password()
        user.password_hash = hash_password(temporary)
        user.must_change_password = True
        user.failed_login_count = 0
        user.locked_until = None
        revoked = await self._revoke_sessions(user_id)
        await self._session.flush()

        await self._audit.record(
            AuditAction.USER_MODIFIED,
            entity_type="USER",
            entity_id=user_id,
            after={"must_change_password": True, "sessions_revoked": revoked},
            detail=(
                f"Password reset for '{user.username}'; {revoked} session"
                f"{'s' if revoked != 1 else ''} revoked. Any lockout was cleared."
            ),
        )
        _ = actor_user_id
        return temporary

    async def roles(self) -> list[RoleRead]:
        """Return the four roles with their permission matrix (§6.10).

        Returns:
            The roles, with user counts.
        """
        result = await self._session.execute(
            select(
                Role.role_id,
                Role.name,
                Role.display_name,
                Role.description,
                func.count(User.user_id).label("user_count"),
            )
            .outerjoin(User, User.role_id == Role.role_id)
            .group_by(Role.role_id, Role.name, Role.display_name, Role.description)
            .order_by(Role.role_id)
        )
        return [
            RoleRead(
                role_id=row.role_id,
                name=row.name,
                display_name=row.display_name,
                description=row.description,
                user_count=row.user_count,
                permissions=ROLE_PERMISSIONS.get(row.name, []),
            )
            for row in result.all()
        ]

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _assert_trainer_fields(payload: UserCreateInput) -> None:
        """Refuse a trainer account missing anything the profile needs.

        Every one of these columns is ``NOT NULL`` on `trainers`. Checking here turns a
        database integrity error into a 422 that names the fields — the difference
        between "something went wrong on our side" and "you left the station blank".

        Args:
            payload: The submitted account.

        Raises:
            ValidationError: Listing every missing field, not just the first.
        """
        required = {
            "stationId": payload.station_id,
            "directorateId": payload.directorate_id,
            "forceNumber": payload.force_number,
            "contactNumber": payload.contact_number,
            "rankId": payload.rank_id,
        }
        missing = [field for field, value in required.items() if not value]
        if not missing:
            return
        raise ValidationError(
            "A trainer account needs "
            + ", ".join(missing)
            + ". Without them the profile cannot be ranked, and the account would "
            "exist but not work.",
            errors=[
                {"field": field, "message": "Required for a trainer account."}
                for field in missing
            ],
        )

    async def _load(self, user_id: int) -> User:
        """Load a user entity or raise."""
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError("That user account could not be found.")
        return user

    async def _role_by_name(self, name: str) -> Role:
        """Resolve a role name to its row.

        Args:
            name: The machine name.

        Returns:
            The role.

        Raises:
            NotFoundError: If no such role exists.
        """
        result = await self._session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            permitted = ", ".join(r.value for r in RoleName)
            raise NotFoundError(f"'{name}' is not a role. Choose one of: {permitted}.")
        return role

    async def _assert_unique(
        self, username: str | None, email: str | None, *, exclude_user_id: int | None = None
    ) -> None:
        """Refuse a duplicate username or email.

        Checked here for a clear message; the database's ``UNIQUE`` constraints are what
        actually guarantee it under concurrency.

        Args:
            username: The username to check, or None.
            email: The email to check, or None.
            exclude_user_id: Ignore this user — used when editing.

        Raises:
            ConflictError: If either is taken.
        """
        conditions = []
        if username:
            conditions.append(User.username == username)
        if email:
            conditions.append(User.email == email)
        if not conditions:
            return
        query = select(User.username, User.email).where(or_(*conditions))
        if exclude_user_id is not None:
            query = query.where(User.user_id != exclude_user_id)
        result = await self._session.execute(query)
        for row in result.all():
            if username and row.username == username:
                raise ConflictError(f"The username '{username}' is already in use.")
            if email and row.email == email:
                raise ConflictError(f"The email address '{email}' is already in use.")

    async def _assert_not_last_administrator(self, user: User, verb: str) -> None:
        """Refuse to remove the last active System Administrator (§6.10).

        Args:
            user: The account being changed.
            verb: For the message — "deactivated" or "suspended".

        Raises:
            ConflictError: If this is the last one.
        """
        role = await self._session.get(Role, user.role_id)
        if role is None or role.name != RoleName.SYSTEM_ADMINISTRATOR:
            return
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .join(Role, Role.role_id == User.role_id)
            .where(
                Role.name == RoleName.SYSTEM_ADMINISTRATOR,
                User.account_status == AccountStatus.ACTIVE.value,
                User.user_id != user.user_id,
            )
        )
        if int(result.scalar_one()) == 0:
            raise ConflictError(
                f"This is the last active System Administrator and cannot be {verb}. "
                "Create or reactivate another one first — otherwise nobody can manage "
                "users, and recovering the system would need direct database access."
            )

    async def _revoke_sessions(self, user_id: int) -> int:
        """Revoke every live refresh token for a user.

        Args:
            user_id: Whose sessions.

        Returns:
            How many were revoked.
        """
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
        tokens = list(result.scalars().all())
        now = self._clock.now()
        for token in tokens:
            token.revoked_at = now
        await self._session.flush()
        return len(tokens)
