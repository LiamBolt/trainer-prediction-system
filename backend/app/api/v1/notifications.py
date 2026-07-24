"""Notification routes (§6.12).

**Every route here is scoped to the caller**, taken from the token. There is no
`recipientId` parameter anywhere on this router. The frontend currently sends one
(`GET /notifications?recipientId=<id>`); honouring it would let any signed-in user read
anyone else's notifications by changing a number — recorded as conflict B4 in
`PROGRESS.md` and corrected in the frontend rather than reproduced here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import ClockDep, CurrentUser, DbSession
from app.schemas.base import Message
from app.schemas.notification import NotificationRead, UnreadCount
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_service(session: DbSession, clock: ClockDep) -> NotificationService:
    """Construct the notification service."""
    return NotificationService(session, clock)


ServiceDep = Annotated[NotificationService, Depends(get_service)]


@router.get(
    "",
    summary="My notifications",
    description=(
        "The caller's own notifications, newest first.\n\n"
        "**Scoped to the token, not to a parameter.** A `recipientId` query parameter "
        "is deliberately absent: identity that arrives in the URL is identity the "
        "client can change."
    ),
    response_model=list[NotificationRead],
    responses={200: {"description": "The caller's notifications."}},
)
async def list_notifications(
    user: CurrentUser,
    service: ServiceDep,
    notification_status: Annotated[
        str | None, Query(alias="status", description="UNREAD or READ.")
    ] = None,
    notification_type: Annotated[
        str | None, Query(alias="type", description="ASSIGNMENT, APPROVAL, EVALUATION, …")
    ] = None,
) -> list[NotificationRead]:
    """Return the caller's notifications."""
    return await service.list_for(
        user.user_id, status=notification_status, notification_type=notification_type
    )


@router.get(
    "/unread-count",
    summary="Unread count for the top-bar badge",
    response_model=UnreadCount,
    responses={200: {"description": "How many are unread."}},
)
async def unread_count(user: CurrentUser, service: ServiceDep) -> UnreadCount:
    """Return the caller's unread count."""
    return UnreadCount(unread=await service.unread_count(user.user_id))


@router.patch(
    "/{notification_id}/read",
    summary="Mark one notification read",
    description=(
        "404 rather than 403 when the notification belongs to someone else. The two "
        "cases are deliberately indistinguishable: a 403 would confirm the existence "
        "of a record the caller is not entitled to know about."
    ),
    response_model=NotificationRead,
    responses={
        200: {"description": "Marked read."},
        404: {"description": "No such notification for this caller."},
    },
)
async def mark_read(
    notification_id: int, user: CurrentUser, service: ServiceDep
) -> NotificationRead:
    """Mark one of the caller's notifications read."""
    return await service.mark_read(notification_id, user.user_id)


@router.post(
    "/read-all",
    summary="Mark every notification read",
    response_model=Message,
    responses={200: {"description": "How many were cleared."}},
)
async def read_all(user: CurrentUser, service: ServiceDep) -> Message:
    """Clear the caller's unread notifications."""
    changed = await service.mark_all_read(user.user_id)
    return Message(
        message=(
            f"{changed} notification{'s' if changed != 1 else ''} marked read."
            if changed
            else "You had no unread notifications."
        )
    )
