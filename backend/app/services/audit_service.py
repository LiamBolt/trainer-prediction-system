"""The audit service (FR-13, B8, §7.2).

**Every mutation writes an audit entry, in the same transaction as the mutation.**
Not "afterwards", not "best effort", not in a background task. If the mutation rolls
back, the entry rolls back with it; if the entry cannot be written, the whole operation
fails.

The asymmetry matters: an audit log that is *incomplete* is worse than no audit log,
because it is trusted. An investigator reading a trail with no entry for an action
concludes the action did not happen. Making the write atomic with the mutation is what
makes that conclusion sound.

Actor, IP, and user agent come from the request-scoped contextvar populated by
:class:`~app.middleware.audit_context.AuditContextMiddleware`, so services do not carry
an ``actor`` parameter through every signature — the parameter that gets dropped on the
one path nobody tested.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.audit_context import get_audit_context
from app.models.enums import AuditAction
from app.models.system import AuditLog

#: Field names never written to ``before_json`` or ``after_json``, whatever the caller
#: passes. An explicit denylist over an allowlist would be safer, but would require
#: every caller to enumerate its safe fields; these are the only secrets the schema
#: holds, and they are removed unconditionally (§7.2).
REDACTED_FIELDS = frozenset(
    {
        "password",
        "password_hash",
        "new_password",
        "current_password",
        "temporary_password",
        "token",
        "token_hash",
        "refresh_token",
        "access_token",
    }
)

REDACTED = "[redacted]"


def _scrub(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove secrets from an audit snapshot.

    Args:
        payload: The snapshot, or None.

    Returns:
        A copy with sensitive values replaced, or None.
    """
    if payload is None:
        return None
    return {
        key: (REDACTED if key.lower() in REDACTED_FIELDS else value)
        for key, value in payload.items()
    }


class AuditService:
    """Writes audit entries within the caller's transaction.

    Args:
        session: The request's session. The service **never** commits — the caller
            owns the transaction boundary, which is what keeps the audit write atomic
            with the mutation it describes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        action: AuditAction,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        detail: str | None = None,
        actor_user_id: int | None = None,
        actor_role: str | None = None,
    ) -> AuditLog:
        """Record an auditable action.

        ``before`` and ``after`` hold **only the changed fields**, not whole entities.
        A full-entity snapshot on every update would make the audit table larger than
        the data it describes, and would bury the one field that actually changed.

        Args:
            action: What happened.
            entity_type: The kind of record affected, e.g. ``"ALLOCATION"``.
            entity_id: Its primary key.
            before: Changed fields as they were.
            after: Changed fields as they now are.
            detail: A human-readable summary, shown in the audit viewer.
            actor_user_id: Overrides the context actor. Used by the login path, where
                the actor is known before the request is authenticated.
            actor_role: Overrides the context role.

        Returns:
            The pending audit row, flushed so its id is available.
        """
        context = get_audit_context()
        entry = AuditLog(
            actor_user_id=actor_user_id if actor_user_id is not None else context.actor_user_id,
            actor_role=actor_role if actor_role is not None else context.actor_role,
            action=action.value,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=_scrub(before),
            after_json=_scrub(after),
            detail=detail,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        self._session.add(entry)
        # Flush, not commit: the id becomes available for chained entries while the
        # transaction stays open and under the caller's control.
        await self._session.flush()
        return entry

    async def record_unauthorised(self, detail: str) -> None:
        """Record a rejected authorisation attempt (NFR-04).

        Args:
            detail: What was attempted.
        """
        await self.record(AuditAction.UNAUTHORISED_ATTEMPT, detail=detail)
