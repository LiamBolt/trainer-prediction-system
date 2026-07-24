"""Authentication: sign-in, lockout, refresh rotation, reuse detection (FR-01, B5).

This module imports **no** `fastapi` (B7). It raises domain exceptions from
:mod:`app.core.exceptions`; the handler layer translates them.

Three behaviours here are security-critical and each has a specific failure mode:

- **Uniform failure messages.** A login endpoint that says "no such user" for one
  input and "wrong password" for another is a user-enumeration oracle. Every failure
  path returns the same shape and the same wording.
- **Three-strike lockout** (FR-01) persisted on the user row, so it survives a process
  restart — an attacker who can crash the service must not thereby clear the counter.
- **Refresh rotation with reuse detection.** Presenting an already-rotated token means
  it was captured, because the legitimate holder would have the newest one. The whole
  family is revoked.
"""

from __future__ import annotations

import datetime
import uuid
from typing import NoReturn

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.constants import LOCKOUT_MINUTES, MAX_LOGIN_ATTEMPTS
from app.core.exceptions import (
    AccountDeactivatedError,
    AccountLockedError,
    UnauthorisedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_token_family,
    verify_password,
)
from app.models.enums import AccountStatus, AuditAction
from app.models.identity import RefreshToken, User
from app.models.reference import PoliceRank, Role
from app.models.trainer import Trainer
from app.schemas.auth import AuthSession, UserSummary
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)

#: The single message returned for every failed sign-in, whatever the cause.
INVALID_CREDENTIALS_MESSAGE = "The username or password is incorrect."


class AuthService:
    """Sign-in, token issue, and token rotation.

    Args:
        session: The request's session.
        settings: Application settings.
        clock: Injected clock — lockout windows and token expiry depend on it, so it
            must be controllable in tests.
        audit: The audit service, sharing the same transaction.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        clock: Clock,
        audit: AuditService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        self._audit = audit

    async def _persist_then_raise(self, error: Exception) -> NoReturn:
        """Commit the failure bookkeeping, then raise.

        Failed sign-ins are the one place where a **rejected** request must still
        write. The three-strike counter (FR-01) and the ``LOGIN_FAILED`` audit entry
        are the record of the attempt, and the request-scoped session rolls back on
        any exception — so raising without committing first silently discards both,
        and the account never locks however many times it is attacked.

        Committing here rather than weakening the dependency's rollback keeps the
        general rule intact: a failed request writes nothing *unless a service
        deliberately decides otherwise*, in one visible place.

        Args:
            error: The exception to raise once the write is durable.

        Raises:
            Exception: Always — the exception passed in.
        """
        await self._session.commit()
        raise error

    async def _load_user(self, username: str) -> User | None:
        """Load a user by username or email, case-insensitively.

        Both columns are ``CITEXT``, so the comparison is case-insensitive in the
        database rather than by lowering in Python — which would miss any row whose
        stored casing differs.

        Args:
            username: The supplied identifier.

        Returns:
            The user, or None.
        """
        result = await self._session.execute(
            select(User).where((User.username == username) | (User.email == username))
        )
        return result.scalar_one_or_none()

    async def _summarise(self, user: User) -> UserSummary:
        """Build the public summary of a user, including their role and trainer link.

        Args:
            user: The user entity.

        Returns:
            The summary returned to the client.
        """
        result = await self._session.execute(
            select(
                Role.name.label("role"),
                PoliceRank.code.label("rank_code"),
                Trainer.trainer_id,
            )
            .select_from(User)
            .join(Role, Role.role_id == User.role_id)
            .outerjoin(PoliceRank, PoliceRank.rank_id == User.rank_id)
            .outerjoin(Trainer, Trainer.user_id == User.user_id)
            .where(User.user_id == user.user_id)
        )
        row = result.one()
        return UserSummary(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            role_id=user.role_id,
            role=row.role,
            rank_code=row.rank_code,
            account_status=user.account_status,
            trainer_id=row.trainer_id,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    async def _issue_session(
        self, user: User, *, family_id: uuid.UUID | None = None
    ) -> AuthSession:
        """Issue an access + refresh pair.

        Args:
            user: The authenticated user.
            family_id: Reuse an existing rotation family, or start a new one.

        Returns:
            The session payload.
        """
        now = self._clock.now()
        summary = await self._summarise(user)
        access_token, expires_at = create_access_token(
            user_id=user.user_id,
            username=user.username,
            role=summary.role,
            trainer_id=summary.trainer_id,
            now=now,
            settings=self._settings,
        )
        refresh_token = generate_refresh_token()
        self._session.add(
            RefreshToken(
                user_id=user.user_id,
                token_hash=hash_refresh_token(refresh_token),
                family_id=family_id or new_token_family(),
                expires_at=now + datetime.timedelta(days=self._settings.refresh_token_expire_days),
            )
        )
        await self._session.flush()
        return AuthSession(
            token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            user=summary,
        )

    async def login(self, username: str, password: str) -> AuthSession:
        """Authenticate a user (FR-01).

        Implements the three-strike, fifteen-minute lockout. Every failure path emits
        the same message so the endpoint cannot be used to discover which usernames
        exist.

        Args:
            username: Username or email.
            password: Plaintext password.

        Returns:
            The issued session.

        Raises:
            UnauthorisedError: Credentials are wrong, or the account does not exist.
            AccountLockedError: The account is within its lockout window.
            AccountDeactivatedError: The account has been deactivated (FR-12).
        """
        now = self._clock.now()
        user = await self._load_user(username)

        if user is None:
            # Audited with no actor — there is no user to attribute it to, and
            # inventing one would corrupt the trail.
            await self._audit.record(
                AuditAction.LOGIN_FAILED,
                detail=f"Sign-in attempt for unknown username '{username[:64]}'.",
            )
            await self._persist_then_raise(UnauthorisedError(INVALID_CREDENTIALS_MESSAGE))

        if user.account_status == AccountStatus.DEACTIVATED:
            await self._audit.record(
                AuditAction.LOGIN_FAILED,
                entity_type="USER",
                entity_id=user.user_id,
                detail="Sign-in attempt on a deactivated account.",
                actor_user_id=user.user_id,
            )
            await self._persist_then_raise(
                AccountDeactivatedError(
                    "This account has been deactivated. Contact your System Administrator."
                )
            )

        if user.locked_until is not None and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            raise AccountLockedError(
                f"This account is locked after {MAX_LOGIN_ATTEMPTS} failed sign-in attempts. "
                f"Try again in {max(1, remaining // 60)} minute(s).",
                retry_after_seconds=remaining,
                unlockAt=user.locked_until.isoformat(),
            )

        if not verify_password(password, user.password_hash, self._settings):
            user.failed_login_count += 1
            detail = "Failed sign-in: incorrect password."

            if user.failed_login_count >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_count = 0
                await self._audit.record(
                    AuditAction.LOGIN_FAILED,
                    entity_type="USER",
                    entity_id=user.user_id,
                    detail=detail,
                    actor_user_id=user.user_id,
                )
                await self._audit.record(
                    AuditAction.ACCOUNT_LOCKED,
                    entity_type="USER",
                    entity_id=user.user_id,
                    detail=(
                        f"Account locked for {LOCKOUT_MINUTES} minutes after "
                        f"{MAX_LOGIN_ATTEMPTS} consecutive failed attempts (FR-01)."
                    ),
                    actor_user_id=user.user_id,
                )
                await self._persist_then_raise(
                    AccountLockedError(
                        f"This account is now locked for {LOCKOUT_MINUTES} minutes after "
                        f"{MAX_LOGIN_ATTEMPTS} failed sign-in attempts.",
                        retry_after_seconds=LOCKOUT_MINUTES * 60,
                        unlockAt=user.locked_until.isoformat(),
                    )
                )

            await self._audit.record(
                AuditAction.LOGIN_FAILED,
                entity_type="USER",
                entity_id=user.user_id,
                detail=detail,
                actor_user_id=user.user_id,
            )
            await self._persist_then_raise(
                UnauthorisedError(
                    INVALID_CREDENTIALS_MESSAGE,
                    attemptsRemaining=MAX_LOGIN_ATTEMPTS - user.failed_login_count,
                )
            )

        if user.account_status == AccountStatus.SUSPENDED:
            await self._audit.record(
                AuditAction.LOGIN_FAILED,
                entity_type="USER",
                entity_id=user.user_id,
                detail="Sign-in attempt on a suspended account.",
                actor_user_id=user.user_id,
            )
            await self._persist_then_raise(
                AccountDeactivatedError(
                    "This account is suspended. Contact your System Administrator."
                )
            )

        # Success. Reset the counter and lift any expired lock.
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now

        # Transparently upgrade the stored hash if policy has strengthened since it
        # was written, so raising the cost never forces a password reset.
        if needs_rehash(user.password_hash, self._settings):
            user.password_hash = hash_password(password, self._settings)

        session = await self._issue_session(user)
        await self._audit.record(
            AuditAction.LOGIN_SUCCESS,
            entity_type="USER",
            entity_id=user.user_id,
            detail="Signed in.",
            actor_user_id=user.user_id,
            actor_role=session.user.role,
        )
        return session

    async def refresh(self, refresh_token: str) -> AuthSession:
        """Rotate a refresh token (B5).

        Presenting a token that has already been revoked means it was captured — the
        legitimate holder would be presenting the newest one. The entire family is
        revoked rather than just the presented token, because the attacker may already
        hold a descendant of it.

        Args:
            refresh_token: The presented token.

        Returns:
            A fresh access + refresh pair in the same family.

        Raises:
            UnauthorisedError: The token is unknown, expired, or already used.
        """
        now = self._clock.now()
        token_hash = hash_refresh_token(refresh_token)
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()

        if stored is None:
            raise UnauthorisedError("Your session has expired. Please sign in again.")

        if stored.revoked_at is not None:
            # Reuse detected. Revoke the whole family and make the holder sign in.
            await self._session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.family_id == stored.family_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await self._audit.record(
                AuditAction.UNAUTHORISED_ATTEMPT,
                entity_type="USER",
                entity_id=stored.user_id,
                detail=(
                    "A refresh token that had already been used was presented again. "
                    "All sessions in that family were revoked as a precaution."
                ),
                actor_user_id=stored.user_id,
            )
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=stored.user_id,
                family_id=str(stored.family_id),
            )
            await self._persist_then_raise(
                UnauthorisedError("Your session has expired. Please sign in again.")
            )

        if stored.expires_at <= now:
            raise UnauthorisedError("Your session has expired. Please sign in again.")

        user = await self._session.get(User, stored.user_id)
        if user is None or user.account_status != AccountStatus.ACTIVE:
            raise UnauthorisedError("Your session has expired. Please sign in again.")

        stored.revoked_at = now
        session = await self._issue_session(user, family_id=stored.family_id)
        await self._audit.record(
            AuditAction.TOKEN_REFRESHED,
            entity_type="USER",
            entity_id=user.user_id,
            detail="Access token refreshed.",
            actor_user_id=user.user_id,
        )
        return session

    async def logout(self, user_id: int) -> None:
        """Revoke every live refresh token for a user.

        Revokes all families, not just the current one: a user clicking "sign out"
        means it, and the alternative leaves a token live on a device they may have
        been trying to log out of.

        Args:
            user_id: The user signing out.
        """
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=self._clock.now())
        )
        await self._audit.record(
            AuditAction.LOGOUT,
            entity_type="USER",
            entity_id=user_id,
            detail="Signed out.",
            actor_user_id=user_id,
        )

    async def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        """Change a password, revoking every session (§6.1).

        Revoking all sessions is the point: a password change is often a response to a
        suspected compromise, and leaving existing tokens live would defeat it.

        Args:
            user_id: The user.
            current_password: Their current password, required as proof of possession.
            new_password: The replacement.

        Raises:
            UnauthorisedError: The current password is wrong.
            ValidationError: The new password is unacceptable.
        """
        user = await self._session.get(User, user_id)
        if user is None:
            raise UnauthorisedError("Your session is not valid. Please sign in again.")

        if not verify_password(current_password, user.password_hash, self._settings):
            raise UnauthorisedError(
                "Your current password is incorrect.",
                errors=[{"field": "currentPassword", "message": "Incorrect password."}],
            )

        if new_password == current_password:
            raise ValidationError(
                "The new password must be different from the current one.",
                errors=[{"field": "newPassword", "message": "Choose a different password."}],
            )

        user.password_hash = hash_password(new_password, self._settings)
        user.must_change_password = False
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=self._clock.now())
        )
        await self._audit.record(
            AuditAction.USER_MODIFIED,
            entity_type="USER",
            entity_id=user_id,
            detail="Password changed. All sessions were signed out.",
            actor_user_id=user_id,
        )
