"""Reading the audit log (FR-13, §6.11). Imports no `fastapi` (B7).

Separate from :mod:`app.services.audit_service`, which writes. The split is deliberate:
that module is imported by every service in the system and must stay small, and this
one is a query surface with filters, two pagination strategies, and a CSV export.

**There is no write path here, and no route on the audit router that could reach one.**
The database trigger from Phase 1 would reject an `UPDATE` or `DELETE` anyway; the
absence of the code is the primary statement, and the trigger is the backstop.
"""

from __future__ import annotations

import csv
import datetime
import io
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models.identity import User
from app.models.system import AuditLog
from app.schemas.admin import AuditEntryRead

#: Offset pagination past this depth is refused. `OFFSET 200000` makes PostgreSQL walk
#: and discard 200,000 rows for every request; on an append-only table that only grows,
#: keyset pagination is the answer, and this is where the caller is told so.
MAX_OFFSET_ROWS = 10_000

#: Columns in the CSV export, in order.
EXPORT_COLUMNS = (
    "log_id",
    "created_at",
    "action",
    "actor_user_id",
    "actor_name",
    "actor_role",
    "entity_type",
    "entity_id",
    "detail",
    "ip_address",
)


class AuditQueryService:
    """Reads the audit log.

    Args:
        session: The request's session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self) -> Select[Any]:
        """Build the projection every audit read shares."""
        return select(
            AuditLog.log_id,
            AuditLog.actor_user_id,
            User.full_name.label("actor_name"),
            AuditLog.actor_role,
            AuditLog.action,
            AuditLog.entity_type,
            AuditLog.entity_id,
            AuditLog.before_json,
            AuditLog.after_json,
            AuditLog.detail,
            AuditLog.ip_address,
            AuditLog.user_agent,
            AuditLog.created_at,
        ).outerjoin(User, User.user_id == AuditLog.actor_user_id)

    @staticmethod
    def apply_filters(
        query: Select[Any],
        *,
        action: str | None = None,
        actor_user_id: int | None = None,
        role: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        search: str | None = None,
    ) -> Select[Any]:
        """Apply audit filters (§6.11).

        Args:
            query: The base query.
            action: One audit action.
            actor_user_id: Who acted.
            role: The actor's role at the time — not their role now, which is the point
                of storing it on the row.
            entity_type: e.g. ``"ALLOCATION"``.
            entity_id: Its primary key.
            date_from: On or after.
            date_to: On or before, inclusive of the whole day.
            search: Free text over the detail sentence.

        Returns:
            The filtered query.
        """
        if action:
            query = query.where(AuditLog.action == action)
        if actor_user_id is not None:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if role:
            query = query.where(AuditLog.actor_role == role)
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.where(AuditLog.entity_id == entity_id)
        if date_from is not None:
            query = query.where(AuditLog.created_at >= date_from)
        if date_to is not None:
            query = query.where(AuditLog.created_at < date_to + datetime.timedelta(days=1))
        if search:
            query = query.where(AuditLog.detail.ilike(f"%{search}%"))
        return query

    async def count(self, query: Select[Any]) -> int:
        """Count rows a filtered query would return."""
        result = await self._session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one())

    async def page(
        self, query: Select[Any], *, offset: int, limit: int
    ) -> list[AuditEntryRead]:
        """Fetch one offset page, newest first.

        Args:
            query: The filtered query.
            offset: Rows to skip.
            limit: Rows to take.

        Returns:
            The entries.

        Raises:
            ValueError: If the offset is past :data:`MAX_OFFSET_ROWS`.
        """
        if offset > MAX_OFFSET_ROWS:
            raise ValueError(
                f"Offset pagination stops at {MAX_OFFSET_ROWS:,} rows. Use the `after` "
                "cursor to page deeper — the audit log only grows, and counting past "
                "this depth costs more every month."
            )
        result = await self._session.execute(
            query.order_by(AuditLog.created_at.desc(), AuditLog.log_id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [AuditEntryRead.model_validate(row) for row in result.all()]

    async def keyset(
        self, query: Select[Any], *, after: str | None, limit: int
    ) -> tuple[list[AuditEntryRead], str | None, bool]:
        """Fetch one keyset page, newest first (§6.11).

        The documented path for deep paging and for the export. Cost is constant
        whatever the depth, because the database seeks rather than counts.

        Args:
            query: The filtered query.
            after: An opaque cursor from a previous page.
            limit: Rows to take.

        Returns:
            The entries, the next cursor, and whether more follow.
        """
        if after:
            cursor_at, cursor_id = decode_cursor(after)
            query = query.where(
                (AuditLog.created_at, AuditLog.log_id) < (cursor_at, cursor_id)  # type: ignore[operator]
            )
        # One extra row answers "is there more?" without a second COUNT.
        result = await self._session.execute(
            query.order_by(AuditLog.created_at.desc(), AuditLog.log_id.desc()).limit(limit + 1)
        )
        rows = result.all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        entries = [AuditEntryRead.model_validate(row) for row in rows]
        next_cursor = (
            encode_cursor(rows[-1].created_at, rows[-1].log_id) if rows and has_more else None
        )
        return entries, next_cursor, has_more

    async def for_entity(self, entity_type: str, entity_id: int) -> list[AuditEntryRead]:
        """Return every action against one record, oldest first (§6.11).

        This is what makes a decision reviewable a year later: one allocation's whole
        history, from approval through the trainer's answer to the evaluation, in the
        order it happened.

        Args:
            entity_type: e.g. ``"ALLOCATION"``.
            entity_id: Its primary key.

        Returns:
            The entries, chronologically.
        """
        result = await self._session.execute(
            self.base_query()
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at, AuditLog.log_id)
        )
        return [AuditEntryRead.model_validate(row) for row in result.all()]

    async def stream_csv(self, query: Select[Any], *, chunk: int = 1000) -> AsyncIterator[str]:
        """Stream the filtered log as CSV (§6.11).

        Yields rows in batches rather than materialising the file. An audit log with
        five years of history does not fit in the memory of a container sized for a
        web API, and discovering that during an inspection is not the moment.

        Args:
            query: The filtered query.
            chunk: Rows per database round trip.

        Yields:
            CSV text, header first.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(EXPORT_COLUMNS)
        yield buffer.getvalue()

        cursor: tuple[datetime.datetime, int] | None = None
        while True:
            page = query.order_by(AuditLog.created_at.desc(), AuditLog.log_id.desc())
            if cursor is not None:
                page = page.where(
                    (AuditLog.created_at, AuditLog.log_id) < cursor  # type: ignore[operator]
                )
            result = await self._session.execute(page.limit(chunk))
            rows = result.all()
            if not rows:
                return

            buffer = io.StringIO()
            writer = csv.writer(buffer)
            for row in rows:
                writer.writerow([getattr(row, column, "") for column in EXPORT_COLUMNS])
            yield buffer.getvalue()

            if len(rows) < chunk:
                return
            cursor = (rows[-1].created_at, rows[-1].log_id)
