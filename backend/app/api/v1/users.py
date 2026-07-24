"""User administration and roles (FR-12, §6.10).

Every route on the users router is **System Administrator only**. That is not caution:
these endpoints create accounts, change roles, and revoke sessions, and the role that
exists to do those things is the only one that should be able to.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import ClockDep, CurrentUser, DbSession, require_roles
from app.core.pagination import Page, PageQuery
from app.models.enums import RoleName
from app.models.identity import User
from app.schemas.admin import (
    PasswordReset,
    RoleRead,
    UserCreated,
    UserCreateInput,
    UserRead,
    UserUpdateInput,
)
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

#: §6.10 puts the roles listing on its own path, and it is readable by Administrators
#: as well — the Roles screen is a reference table, not a privileged operation.
roles_router = APIRouter(prefix="/roles", tags=["Roles"])

TA = RoleName.TRAINING_ADMINISTRATOR
SA = RoleName.SYSTEM_ADMINISTRATOR

SORTABLE = {
    "username": User.username,
    "fullName": User.full_name,
    "createdAt": User.created_at,
    "lastLoginAt": User.last_login_at,
    "accountStatus": User.account_status,
}


def get_service(session: DbSession, clock: ClockDep) -> UserService:
    """Construct the user service."""
    return UserService(session, AuditService(session), clock)


ServiceDep = Annotated[UserService, Depends(get_service)]


@router.get(
    "",
    summary="List users",
    description=(
        "Filterable by role, account status, and free text over username, name and "
        "email.\n\n"
        "Returned in the standard paginated envelope. There are forty-odd accounts "
        "today, but *every* list endpoint uses the envelope — an unpaginated list is a "
        "latent problem waiting for the system to succeed."
    ),
    response_model=Page[UserRead],
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {"description": "A page of users."},
        403: {"description": "System Administrator only."},
    },
)
async def list_users(
    session: DbSession,
    user: CurrentUser,
    service: ServiceDep,
    params: PageQuery,
    search: Annotated[str | None, Query(description="Username, name, or email.")] = None,
    role: Annotated[str | None, Query(description="Role name.")] = None,
    account_status: Annotated[str | None, Query(alias="status")] = None,
) -> Page[UserRead]:
    """Return a page of users."""
    _ = user
    query = service.apply_filters(
        service.list_query(), search=search, role=role, account_status=account_status
    )
    total = await service.count(query)
    ordering = params.resolve_sort(SORTABLE, User.username)
    rows = await session.execute(query.order_by(ordering).offset(params.offset).limit(params.limit))
    return Page[UserRead].build(
        [UserRead.model_validate(row) for row in rows.all()], total=total, params=params
    )


@router.post(
    "",
    summary="Create a user (FR-12)",
    description=(
        "Creates the account with a **generated** temporary password and "
        "`mustChangePassword = true`.\n\n"
        "The caller does not choose the password. An initial password chosen by an "
        "administrator travels by whatever channel they use to pass it on, and is very "
        "often reused.\n\n"
        "If the role is `TRAINER`, the linked trainer profile is created **in the same "
        "transaction** — a Trainer account without a profile cannot see assignments and "
        "cannot be ranked, which is a broken state that must be impossible rather than "
        "merely unlikely. `stationId` and `forceNumber` are therefore required for that "
        "role.\n\n"
        "`temporaryPassword` is in the response body **once**. It is never logged, "
        "never stored in plaintext, and cannot be retrieved again."
    ),
    response_model=UserCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(SA))],
    responses={
        201: {"description": "Created. The temporary password is shown once."},
        403: {"description": "System Administrator only."},
        409: {"description": "The username or email is already in use."},
        422: {"description": "A trainer account was submitted without a posting."},
    },
)
async def create_user(
    payload: UserCreateInput, user: CurrentUser, service: ServiceDep, response: Response
) -> UserCreated:
    """Create a user account (FR-12)."""
    created, temporary = await service.create(payload, user.user_id)
    response.headers["Location"] = f"/api/v1/users/{created.user_id}"
    return UserCreated(
        user=created,
        temporary_password=temporary,
        message=(
            f"Account created for {created.full_name}. Give them this password once — "
            "it is not stored and cannot be shown again. They must change it at first "
            "sign-in."
        ),
    )


@router.get(
    "/{user_id}",
    summary="One user",
    response_model=UserRead,
    dependencies=[Depends(require_roles(SA))],
    responses={200: {"description": "The user."}, 404: {"description": "No such user."}},
)
async def get_user(user_id: int, user: CurrentUser, service: ServiceDep) -> UserRead:
    """Return one user."""
    _ = user
    return await service.get(user_id)


@router.patch(
    "/{user_id}",
    summary="Edit a user (FR-12)",
    description=(
        "A **role change takes effect at the next sign-in** — the role travels in the "
        "access token. Rather than leave that as a surprise, the response says so, and "
        "the user's refresh sessions are revoked so the change lands within the access "
        "token's fifteen-minute lifetime rather than at its leisure.\n\n"
        "`accountStatus` accepts `ACTIVE` or `SUSPENDED`. Deactivation has its own "
        "endpoint because it must also revoke sessions."
    ),
    response_model=UserRead,
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {"description": "Updated."},
        403: {"description": "System Administrator only."},
        409: {
            "description": (
                "The email is taken, deactivation was attempted here, or this is the "
                "last active System Administrator."
            )
        },
    },
)
async def update_user(
    user_id: int,
    payload: UserUpdateInput,
    user: CurrentUser,
    service: ServiceDep,
    response: Response,
) -> UserRead:
    """Edit a user account."""
    updated, role_note = await service.update(user_id, payload, user.user_id)
    if role_note:
        # A header rather than a body field: the response shape is `UserRead`, and the
        # note is about the *effect* of the change rather than the user's state.
        response.headers["X-TPS-Notice"] = role_note
    return updated


@router.post(
    "/{user_id}/deactivate",
    summary="Deactivate a user",
    description=(
        "Sets `DEACTIVATED` and **revokes every session immediately**. A deactivated "
        "user cannot sign in with the correct password, and cannot continue on an "
        "access token issued a minute ago — the account status is re-read from the "
        "database on every request precisely so revocation is immediate.\n\n"
        "**The last active System Administrator cannot be deactivated** (409), and "
        "neither can your own account."
    ),
    response_model=UserRead,
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {"description": "Deactivated, sessions revoked."},
        409: {"description": "Already deactivated, your own account, or the last administrator."},
    },
)
async def deactivate_user(user_id: int, user: CurrentUser, service: ServiceDep) -> UserRead:
    """Deactivate a user account."""
    return await service.deactivate(user_id, user.user_id)


@router.post(
    "/{user_id}/reset-password",
    summary="Reset a user's password",
    description=(
        "Issues a new temporary password, sets `mustChangePassword`, clears any "
        "lockout, and revokes every session. The password is shown once."
    ),
    response_model=PasswordReset,
    dependencies=[Depends(require_roles(SA))],
    responses={200: {"description": "Reset. The temporary password is shown once."}},
)
async def reset_password(user_id: int, user: CurrentUser, service: ServiceDep) -> PasswordReset:
    """Reset a user's password."""
    temporary = await service.reset_password(user_id, user.user_id)
    return PasswordReset(
        temporary_password=temporary,
        message=(
            "Password reset and all sessions revoked. Give them this password once — "
            "it is not stored and cannot be shown again."
        ),
    )


@roles_router.get(
    "",
    summary="The four roles and what each may do",
    description=(
        "Serves the permission matrix as **data**, so the Roles screen is not a "
        "hard-coded table in the frontend that has to be edited in two places to stay "
        "true — and would therefore eventually be true in one."
    ),
    response_model=list[RoleRead],
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "The roles, with user counts and permissions."}},
)
async def list_roles(user: CurrentUser, service: ServiceDep) -> list[RoleRead]:
    """Return the roles and their permissions."""
    _ = user
    return await service.roles()
