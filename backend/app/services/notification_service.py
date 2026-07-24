"""Notifications (§6.12). Imports no `fastapi` (B7).

**Creation is in-transaction; dispatch is not.** A notification row is written in the
same transaction as the allocation that caused it, so there can never be a notified
trainer without an allocation, or an allocation nobody was told about. Actually
*delivering* it — the part that talks to something outside this process — happens in a
background task after the response has been sent, because a slow mail relay must not
delay an approval.

Failures are recorded as ``delivery_status = 'FAILED'`` and surface on the System
Health screen. They are never swallowed: a notification that silently did not arrive is
worse than one that visibly did not.
"""

from __future__ import annotations

import datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import NotFoundError
from app.models.enums import DeliveryStatus, NotificationStatus, NotificationType
from app.models.system import Notification
from app.schemas.notification import NotificationRead

logger = structlog.get_logger(__name__)


class NotificationService:
    """Creates and reads notifications.

    Args:
        session: The request's session.
        clock: Injected clock.
    """

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def create(
        self,
        *,
        recipient_user_id: int,
        message: str,
        notification_type: NotificationType,
        link_to: str | None = None,
    ) -> Notification:
        """Queue a notification inside the caller's transaction.

        Args:
            recipient_user_id: Who is being told.
            message: What they are told, written for the reader.
            notification_type: The category driving the icon and grouping.
            link_to: A frontend route the notification links to.

        Returns:
            The pending row, flushed so its id is available to the dispatcher.
        """
        notification = Notification(
            recipient_user_id=recipient_user_id,
            message=message,
            type=notification_type.value,
            link_to=link_to,
            status=NotificationStatus.UNREAD.value,
            delivery_status=DeliveryStatus.PENDING.value,
            sent_date=None,
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_for(
        self, user_id: int, *, status: str | None = None, notification_type: str | None = None
    ) -> list[NotificationRead]:
        """Return the caller's notifications, newest first.

        Args:
            user_id: The caller. Never taken from the request body or query string.
            status: Optional UNREAD/READ filter.
            notification_type: Optional category filter.

        Returns:
            The caller's notifications.
        """
        query = select(Notification).where(Notification.recipient_user_id == user_id)
        if status:
            query = query.where(Notification.status == status)
        if notification_type:
            query = query.where(Notification.type == notification_type)
        result = await self._session.execute(query.order_by(Notification.created_at.desc()))
        return [
            NotificationRead(
                notification_id=row.notification_id,
                recipient_id=row.recipient_user_id,
                message=row.message,
                type=row.type,
                sent_date=row.sent_date,
                status=row.status,
                link_to=row.link_to,
                delivery_status=row.delivery_status,
            )
            for row in result.scalars().all()
        ]

    async def unread_count(self, user_id: int) -> int:
        """Count the caller's unread notifications.

        Args:
            user_id: The caller.

        Returns:
            The badge number.
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.status == NotificationStatus.UNREAD.value,
            )
        )
        return int(result.scalar_one())

    async def mark_read(self, notification_id: int, user_id: int) -> NotificationRead:
        """Mark one notification read.

        The recipient check is object-level (B4, layer 2): the role gate admits every
        authenticated user to this route, so ownership is the only thing standing
        between a caller and someone else's message.

        Args:
            notification_id: Primary key.
            user_id: The caller.

        Returns:
            The updated notification.

        Raises:
            NotFoundError: If it does not exist **or** belongs to another user. The two
                cases are deliberately indistinguishable — a 403 here would confirm the
                existence of a record the caller may not see.
        """
        notification = await self._session.get(Notification, notification_id)
        if notification is None or notification.recipient_user_id != user_id:
            raise NotFoundError("That notification could not be found.")
        if notification.status != NotificationStatus.READ.value:
            notification.status = NotificationStatus.READ.value
            notification.read_at = self._clock.now()
            await self._session.flush()
        return NotificationRead(
            notification_id=notification.notification_id,
            recipient_id=notification.recipient_user_id,
            message=notification.message,
            type=notification.type,
            sent_date=notification.sent_date,
            status=notification.status,
            link_to=notification.link_to,
            delivery_status=notification.delivery_status,
        )

    async def mark_all_read(self, user_id: int) -> int:
        """Mark every unread notification of the caller's read.

        Args:
            user_id: The caller.

        Returns:
            How many were changed.
        """
        # Counted before the UPDATE rather than read from ``rowcount``: both run in the
        # same transaction, so the count is exact, and it avoids depending on a driver
        # attribute whose availability varies.
        changed = await self.unread_count(user_id)
        if changed:
            await self._session.execute(
                update(Notification)
                .where(
                    Notification.recipient_user_id == user_id,
                    Notification.status == NotificationStatus.UNREAD.value,
                )
                .values(status=NotificationStatus.READ.value, read_at=self._clock.now())
            )
        return changed


async def dispatch(notification_ids: list[int]) -> None:
    """Deliver queued notifications, as a background task (§6.12).

    Runs **after** the response has been sent, on its own session — the request's
    session is closed by then, and reusing it would be a use-after-free.

    There is no external transport configured yet: no SMS gateway, no mail relay. This
    marks the rows ``SENT`` so the in-application inbox works, and is the single place
    a real transport plugs in later. It does not pretend to have delivered anything
    beyond the application itself, and the ``delivery_status`` column is what a future
    integration will set to ``FAILED`` when a gateway refuses.

    Args:
        notification_ids: Rows to deliver.
    """
    if not notification_ids:
        return
    from app.db.session import SessionLocal

    try:
        async with SessionLocal() as session:
            await session.execute(
                update(Notification)
                .where(
                    Notification.notification_id.in_(notification_ids),
                    Notification.delivery_status == DeliveryStatus.PENDING.value,
                )
                .values(
                    delivery_status=DeliveryStatus.SENT.value,
                    sent_date=datetime.datetime.now(datetime.UTC),
                )
            )
            await session.commit()
    except Exception:
        # A dispatch failure must never surface as a request failure — the allocation
        # it describes is already committed — but it must be visible.
        logger.exception("notification_dispatch_failed", notification_ids=notification_ids)
        await _mark_failed(notification_ids)


async def _mark_failed(notification_ids: list[int]) -> None:
    """Record a failed dispatch so System Health can show it.

    Args:
        notification_ids: Rows that could not be delivered.
    """
    from app.db.session import SessionLocal

    try:
        async with SessionLocal() as session:
            await session.execute(
                update(Notification)
                .where(Notification.notification_id.in_(notification_ids))
                .values(delivery_status=DeliveryStatus.FAILED.value)
            )
            await session.commit()
    except Exception:
        logger.exception("notification_failure_record_failed", notification_ids=notification_ids)
