"""Notification DTOs (§6.12).

Every route on this router is scoped to the **caller**, taken from the token. There is
no ``recipientId`` parameter: the frontend currently sends one, and honouring it would
let any signed-in user read anyone else's notifications by changing a number in the
URL (recorded as conflict B4 in ``PROGRESS.md``).
"""

from __future__ import annotations

import datetime

from pydantic import Field

from app.schemas.base import CamelModel


class NotificationRead(CamelModel):
    """One notification addressed to the caller."""

    notification_id: int
    recipient_id: int
    message: str
    type: str = Field(description="ASSIGNMENT, APPROVAL, EVALUATION, SYSTEM, or REMINDER.")
    sent_date: datetime.datetime | None = Field(
        default=None, description="Null while delivery is still pending."
    )
    status: str = Field(description="UNREAD or READ.")
    link_to: str | None = Field(
        default=None, description="Where the interface should take the reader, e.g. '/assignments/12'."
    )
    delivery_status: str = Field(
        default="PENDING",
        description=(
            "PENDING, SENT, or FAILED. A failure is visible on the System Health screen "
            "rather than swallowed."
        ),
    )


class UnreadCount(CamelModel):
    """The top-bar badge."""

    unread: int = Field(ge=0)
