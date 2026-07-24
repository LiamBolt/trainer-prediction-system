"""System tables — the audit trail and notifications (§5.8)."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, primary_key
from app.db.types import IpAddress, JsonB
from app.models.enums import (
    AuditAction,
    DeliveryStatus,
    NotificationStatus,
    NotificationType,
    check_in,
)

if TYPE_CHECKING:
    from app.models.identity import User


class AuditLog(Base):
    """An append-only record of an auditable action.

    Serves FR-13. Entries **cannot be edited or deleted by any role**, and that is
    enforced by a ``BEFORE UPDATE OR DELETE`` trigger that raises an exception
    (D6, migration 0002). The enforcement sits below the application deliberately: no
    application bug, no stray ORM call, and no administrator at a psql prompt can
    bypass a trigger. An audit trail an administrator can edit is not an audit trail.

    There is no ``updated_at`` column. It would be a lie — nothing here is ever
    updated — and a column that can only ever hold one value is misinformation in the
    data dictionary.

    ``actor_role`` is denormalised from the user's role **at the time of the action**.
    Roles change; an audit entry must record the authority under which an action was
    taken, not the authority its actor happens to hold today. Reading the role through
    ``actor_user_id`` would quietly rewrite history on every promotion.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(check_in("action", AuditAction), name="action_valid"),
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        {
            "comment": (
                "Append-only audit trail (FR-13). UPDATE and DELETE raise an exception "
                "via the prevent_audit_mutation trigger."
            )
        },
    )

    log_id: Mapped[int] = primary_key()
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
        comment="Who acted. NULL for system actions and for failed sign-ins with an unknown username.",
    )
    actor_role: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="The actor's role at the time of the action. Denormalised on purpose.",
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(
        String(60), nullable=True, comment="e.g. 'ALLOCATION'. NULL for session-level actions."
    )
    entity_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="Affected row id. NULL for session-level actions."
    )
    before_json: Mapped[dict[str, Any] | None] = mapped_column(
        JsonB, nullable=True, comment="Prior state. NULL for creations and for read actions."
    )
    after_json: Mapped[dict[str, Any] | None] = mapped_column(
        JsonB, nullable=True, comment="Resulting state. NULL for deletions and for read actions."
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Human-readable summary shown in the audit viewer."
    )
    ip_address: Mapped[str | None] = mapped_column(IpAddress, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    actor: Mapped[User | None] = relationship(lazy="raise_on_sql")


class Notification(Base, TimestampMixin):
    """A message delivered to a user in-app.

    Serves FR-11. ``status`` is what the recipient has done with it; ``delivery_status``
    is what the system managed to do with it. They are different questions: a
    notification can be ``SENT`` and still ``UNREAD``, or ``FAILED`` and therefore
    never readable at all. Collapsing them would hide delivery failures behind an
    unread badge.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(check_in("type", NotificationType), name="type_valid"),
        CheckConstraint(check_in("status", NotificationStatus), name="status_valid"),
        CheckConstraint(check_in("delivery_status", DeliveryStatus), name="delivery_status_valid"),
        CheckConstraint("status <> 'READ' OR read_at IS NOT NULL", name="read_requires_timestamp"),
        # The inbox query: this recipient's unread notifications, newest first.
        Index(
            "ix_notifications_recipient_status_created", "recipient_user_id", "status", "created_at"
        ),
        {"comment": "In-app notifications. FR-11."},
    )

    notification_id: Mapped[int] = primary_key()
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="CASCADE: a deleted user's notifications have no recipient and no meaning.",
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    link_to: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="In-app route, e.g. '/my-assignments'. NULL when there is nowhere to go.",
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=NotificationStatus.UNREAD, server_default="UNREAD"
    )
    delivery_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DeliveryStatus.PENDING, server_default="PENDING"
    )
    sent_date: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="NULL while delivery_status is PENDING."
    )
    read_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="NULL while unread."
    )

    recipient: Mapped[User] = relationship(lazy="raise_on_sql")
