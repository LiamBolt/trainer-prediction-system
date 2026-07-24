"""Authentication routes (§6.1).

``/login`` is rate-limited **independently of account lockout**. They defend different
things: lockout protects one account from a targeted guess; rate limiting protects the
whole login surface from an attacker spraying one common password across many
usernames, which never trips any single account's counter.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import ClockDep, CurrentUser, DbSession, SettingsDep
from app.core.rate_limit import limiter, login_limit
from app.schemas.auth import (
    AuthSession,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    UserSummary,
)
from app.schemas.base import Message
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(session: DbSession, settings: SettingsDep, clock: ClockDep) -> AuthService:
    """Construct the auth service for this request.

    Args:
        session: Request-scoped database session.
        settings: Application settings.
        clock: Injected clock.

    Returns:
        The service, sharing the request's transaction.
    """
    return AuthService(session, settings, clock, AuditService(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/login",
    summary="Sign in",
    description=(
        "Authenticates a username (or email) and password, returning a short-lived "
        "access token and a rotating refresh token.\n\n"
        "**Account lockout (FR-01).** Three consecutive failures lock the account for "
        "15 minutes and return `423` with `retryAfterSeconds`.\n\n"
        "**No user enumeration.** A wrong password and an unknown username return the "
        "identical message. Do not rely on the wording to detect whether an account "
        "exists — it is deliberately uninformative.\n\n"
        "**Deactivated accounts** receive a distinct `403`, because a deactivated user "
        "retyping a correct password forever helps nobody."
    ),
    response_model=AuthSession,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Signed in. Access and refresh tokens issued."},
        401: {"description": "The username or password is incorrect."},
        403: {"description": "The account is deactivated or suspended."},
        423: {"description": "The account is locked after repeated failures."},
        429: {"description": "Too many sign-in attempts from this address."},
    },
)
@limiter.limit(login_limit)
async def login(payload: LoginRequest, service: AuthServiceDep, request: Request) -> AuthSession:
    """Authenticate a user.

    Implements FR-01.

    Args:
        payload: Username and password.
        service: The auth service.
        request: Used by the rate limiter.

    Returns:
        The issued session.
    """
    _ = request  # consumed by the rate-limit decorator applied in main.py
    return await service.login(payload.username, payload.password)


@router.post(
    "/refresh",
    summary="Rotate the refresh token",
    description=(
        "Exchanges a valid refresh token for a new access + refresh pair, revoking the "
        "presented token.\n\n"
        "**Reuse detection.** Presenting a token that was already rotated revokes every "
        "token in the same family and returns `401`. That pattern means the token was "
        "captured — the legitimate holder would be presenting the newest one."
    ),
    response_model=AuthSession,
    responses={
        200: {"description": "A new token pair was issued."},
        401: {"description": "The token is unknown, expired, or already used."},
    },
)
async def refresh(payload: RefreshRequest, service: AuthServiceDep) -> AuthSession:
    """Rotate a refresh token.

    Args:
        payload: The presented refresh token.
        service: The auth service.

    Returns:
        A fresh session.
    """
    return await service.refresh(payload.refresh_token)


@router.post(
    "/logout",
    summary="Sign out",
    description="Revokes every live refresh token for the current user.",
    response_model=Message,
    responses={200: {"description": "Signed out."}, 401: {"description": "Not authenticated."}},
)
async def logout(user: CurrentUser, service: AuthServiceDep) -> Message:
    """Sign the current user out of every session.

    Args:
        user: The authenticated user.
        service: The auth service.

    Returns:
        Acknowledgement.
    """
    await service.logout(user.user_id)
    return Message(message="You have been signed out.")


@router.get(
    "/me",
    summary="The current user",
    description=(
        "Returns the authenticated user with their role, rank, and — when they are a "
        "Trainer — their `trainerId`, which the frontend uses to route to self-service "
        "screens.\n\n"
        "Account status is re-read from the database on every request, so a user "
        "deactivated moments ago is rejected immediately rather than when their access "
        "token happens to expire."
    ),
    response_model=UserSummary,
    responses={
        200: {"description": "The current user."},
        401: {"description": "Not authenticated."},
    },
)
async def me(user: CurrentUser) -> UserSummary:
    """Return the authenticated user.

    Args:
        user: Resolved from the bearer token.

    Returns:
        The user summary.
    """
    return user


@router.post(
    "/change-password",
    summary="Change your password",
    description=(
        "Changes the current user's password. Requires the current password as proof "
        "of possession, and **revokes every session** — a password change is usually a "
        "response to suspected compromise, and leaving old tokens live would defeat it."
    ),
    response_model=Message,
    responses={
        200: {"description": "Password changed. All sessions were signed out."},
        401: {"description": "The current password is incorrect."},
        422: {"description": "The new password was rejected."},
    },
)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, service: AuthServiceDep
) -> Message:
    """Change the current user's password.

    Args:
        payload: Current and new passwords.
        user: The authenticated user.
        service: The auth service.

    Returns:
        Acknowledgement.
    """
    await service.change_password(user.user_id, payload.current_password, payload.new_password)
    return Message(
        message="Your password has been changed. Please sign in again on your other devices."
    )
