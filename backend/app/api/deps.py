"""Shared FastAPI dependencies: session, current user, RBAC, clock, settings.

Dependencies are the seam that makes this API testable. A test overrides the session
and the clock, not the business logic.

**Authorisation is two layers** (§7.1, B4), and both are required:

1. :func:`require_roles` on the route — coarse role gating.
2. An ownership check *inside the service* — "a Trainer may edit **their own** profile".

Role checks alone are the most commonly missed vulnerability class in systems shaped
like this one (OWASP: Broken Object Level Authorization). A route that returns a
resource keyed by a client-supplied id needs the second check even when the role is
right.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, system_clock
from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorisedError
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.middleware.audit_context import set_audit_actor
from app.models.enums import AccountStatus, RoleName
from app.models.identity import User
from app.models.reference import PoliceRank, Role
from app.models.trainer import Trainer
from app.schemas.auth import UserSummary

logger = structlog.get_logger(__name__)

#: ``auto_error=False`` so a missing header raises our own 401 in problem+json shape
#: rather than FastAPI's default body, which would violate B9's single error shape.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token.")


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session, committing on success (§7.3).

    One session per request, one transaction, committed once at the edge. Services
    receive this session; they never create their own, which is what allows a
    multi-step operation — approve, freeze, notify, audit — to be atomic.

    Yields:
        An open :class:`AsyncSession`.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_clock() -> Clock:
    """Return the application clock.

    Overridden in tests so time-dependent behaviour — lockout windows, token expiry,
    confidence recency — is deterministic.
    """
    return system_clock


ClockDep = Annotated[Clock, Depends(get_clock)]


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserSummary:
    """Resolve the authenticated user from the bearer token.

    The token carries the role, but the **account status is re-read from the database**
    on every request. Trusting the token's word alone would leave a deactivated user
    authenticated until their access token expired — up to fifteen minutes after an
    administrator revoked them, which §6.10 explicitly forbids.

    Args:
        request: The incoming request, used to stash the user for logging.
        session: Database session.
        credentials: The parsed ``Authorization: Bearer`` header, if present.

    Returns:
        A summary of the authenticated user.

    Raises:
        UnauthorisedError: If the token is missing, invalid, expired, or the user no
            longer exists.
        ForbiddenError: If the account has since been suspended or deactivated.
    """
    if credentials is None:
        raise UnauthorisedError("Please sign in to continue.")

    claims = decode_access_token(credentials.credentials)
    try:
        user_id = int(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorisedError("Your session is not valid. Please sign in again.") from exc

    result = await session.execute(
        select(
            User.user_id,
            User.username,
            User.full_name,
            User.email,
            User.role_id,
            Role.name.label("role"),
            PoliceRank.code.label("rank_code"),
            User.account_status,
            User.must_change_password,
            User.created_at,
            User.last_login_at,
            Trainer.trainer_id,
        )
        .join(Role, Role.role_id == User.role_id)
        .outerjoin(PoliceRank, PoliceRank.rank_id == User.rank_id)
        .outerjoin(Trainer, Trainer.user_id == User.user_id)
        .where(User.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise UnauthorisedError("Your session is not valid. Please sign in again.")

    if row.account_status == AccountStatus.DEACTIVATED:
        raise ForbiddenError(
            "This account has been deactivated. Contact your System Administrator."
        )
    if row.account_status == AccountStatus.SUSPENDED:
        raise ForbiddenError("This account is suspended. Contact your System Administrator.")

    user = UserSummary.model_validate(row)
    # Populate the audit context now that identity is known; the middleware ran before
    # the token was decoded and could only record the network-level facts.
    set_audit_actor(user.user_id, user.role)
    request.state.user_id = user.user_id
    return user


CurrentUser = Annotated[UserSummary, Depends(get_current_user)]


def require_roles(
    *roles: RoleName,
) -> Callable[[UserSummary], Coroutine[Any, Any, UserSummary]]:
    """Build a dependency admitting only the given roles (B4, layer 1).

    Every authorisation failure writes ``UNAUTHORISED_ATTEMPT`` to the audit log
    (NFR-04). The write is deferred to the audit service via the route's session, so a
    refusal is recorded as reliably as a success — a system that logs only what it
    permitted cannot show what it refused.

    Args:
        *roles: Role names permitted on the route.

    Returns:
        A dependency returning the user, or raising :class:`ForbiddenError`.

    Example:
        >>> @router.post("/", dependencies=[Depends(require_roles(RoleName.TRAINING_ADMINISTRATOR))])
        ... async def approve() -> None: ...
    """
    permitted = {role.value for role in roles}

    async def dependency(user: CurrentUser) -> UserSummary:
        if user.role not in permitted:
            logger.warning(
                "authorisation_denied",
                user_id=user.user_id,
                role=user.role,
                required=sorted(permitted),
            )
            raise ForbiddenError(
                "You do not have permission to perform this action. "
                "If you believe this is wrong, contact your System Administrator."
            )
        return user

    return dependency


def require_trainer_self(user: UserSummary, trainer_id: int) -> None:
    """Assert that a Trainer is acting on their own record (B4, layer 2).

    Administrators and officers pass through; a Trainer may only touch their own
    trainer id. This is the object-level check that role gating cannot express, and
    omitting it is what turns ``/trainers/{id}`` into an information-disclosure bug.

    Args:
        user: The authenticated user.
        trainer_id: The trainer record being accessed.

    Raises:
        ForbiddenError: If a Trainer targets someone else's record.
    """
    if user.role != RoleName.TRAINER:
        return
    if user.trainer_id != trainer_id:
        raise ForbiddenError("You may only view or change your own trainer record.")


def current_trainer_id(user: UserSummary) -> int:
    """Return the caller's trainer id, or refuse.

    Args:
        user: The authenticated user.

    Returns:
        The linked trainer id.

    Raises:
        ForbiddenError: If the account has no linked trainer profile.
    """
    if user.trainer_id is None:
        raise ForbiddenError(
            "This account is not linked to a trainer profile, so it has no assignments."
        )
    return user.trainer_id
