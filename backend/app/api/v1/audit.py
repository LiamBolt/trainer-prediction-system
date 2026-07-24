"""Audit log routes (FR-13, §6.11).

**There is no POST, PATCH, or DELETE on this router, for any role.** The database
trigger installed in Phase 1 would reject a write anyway, but the absence of the route
is the primary statement: the audit log is not a resource this API mutates.

Two pagination strategies are offered, and the reason is honest rather than
accommodating. Keyset (`?after=`) is the documented path — cost is constant at any
depth. Offset is supported because the frontend's table uses it today, and capped at
10,000 rows, beyond which the caller is told to switch.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import ClockDep, CurrentUser, DbSession, require_roles
from app.core.exceptions import ValidationError
from app.core.pagination import CursorPage, Page, PageQuery
from app.models.enums import AuditAction, RoleName
from app.schemas.admin import AuditEntryRead
from app.services.audit_query_service import AuditQueryService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit"])

TA = RoleName.TRAINING_ADMINISTRATOR
SA = RoleName.SYSTEM_ADMINISTRATOR


def get_service(session: DbSession) -> AuditQueryService:
    """Construct the audit query service."""
    return AuditQueryService(session)


ServiceDep = Annotated[AuditQueryService, Depends(get_service)]


@router.get(
    "",
    summary="The audit trail (FR-13)",
    description=(
        "Filterable by action, actor, the actor's role **at the time**, entity, and "
        "date range.\n\n"
        "Pass `after` for keyset pagination — the documented path, and the only one "
        "whose cost does not grow with depth. Without it the endpoint uses offset "
        "pagination, capped at 10,000 rows.\n\n"
        "`actorRole` filters on the role recorded on the entry, not the actor's role "
        "today. That distinction is the whole point of storing it: an officer promoted "
        "last month did not act as an administrator last year."
    ),
    response_model=Page[AuditEntryRead] | CursorPage[AuditEntryRead],
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {"description": "A page of audit entries, newest first."},
        403: {"description": "System Administrator only."},
        422: {"description": "Offset paging past the cap; use the `after` cursor."},
    },
)
async def list_audit(
    user: CurrentUser,
    service: ServiceDep,
    params: PageQuery,
    action: Annotated[str | None, Query(description="One audit action.")] = None,
    actor_user_id: Annotated[int | None, Query(alias="userId")] = None,
    actor_role: Annotated[str | None, Query(alias="role")] = None,
    entity_type: Annotated[str | None, Query(alias="entityType")] = None,
    entity_id: Annotated[int | None, Query(alias="entityId")] = None,
    date_from: Annotated[datetime.date | None, Query(alias="from")] = None,
    date_to: Annotated[datetime.date | None, Query(alias="to")] = None,
    search: Annotated[str | None, Query(description="Free text over the detail sentence.")] = None,
    after: Annotated[str | None, Query(description="Keyset cursor from a previous page.")] = None,
) -> Page[AuditEntryRead] | CursorPage[AuditEntryRead]:
    """Return a page of audit entries.

    Raises:
        ValidationError: If offset paging is taken past its cap.
    """
    _ = user
    query = service.apply_filters(
        service.base_query(),
        action=action,
        actor_user_id=actor_user_id,
        role=actor_role,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )

    if after is not None:
        entries, next_cursor, has_more = await service.keyset(
            query, after=after, limit=params.limit
        )
        return CursorPage[AuditEntryRead](
            items=entries,
            page_size=params.page_size,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    total = await service.count(query)
    try:
        entries = await service.page(query, offset=params.offset, limit=params.limit)
    except ValueError as exc:
        raise ValidationError(str(exc), errors=[{"field": "page", "message": str(exc)}]) from exc
    return Page[AuditEntryRead].build(entries, total=total, params=params)


@router.get(
    "/export",
    summary="Export the audit trail as CSV",
    description=(
        "Streams the filtered log with `StreamingResponse` — the file is never "
        "materialised in memory, because an audit log with five years of history does "
        "not fit in a container sized for a web API, and finding that out during an "
        "inspection is not the moment.\n\n"
        "**The export is itself audited.** Who read the audit log, and with what "
        "filters, is exactly the kind of thing an audit log is for."
    ),
    dependencies=[Depends(require_roles(SA))],
    responses={
        200: {
            "description": "A CSV stream.",
            "content": {"text/csv": {"schema": {"type": "string"}}},
        },
        403: {"description": "System Administrator only."},
    },
)
async def export_audit(
    session: DbSession,
    user: CurrentUser,
    service: ServiceDep,
    clock: ClockDep,
    action: Annotated[str | None, Query()] = None,
    actor_user_id: Annotated[int | None, Query(alias="userId")] = None,
    date_from: Annotated[datetime.date | None, Query(alias="from")] = None,
    date_to: Annotated[datetime.date | None, Query(alias="to")] = None,
) -> StreamingResponse:
    """Stream the audit log as CSV, and audit the export."""
    filters = {
        "action": action,
        "userId": actor_user_id,
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
    }
    applied = {k: v for k, v in filters.items() if v is not None}

    # Written before the stream starts, in the request's transaction, so the record of
    # the export exists whether or not the download completes. An export that failed
    # halfway still means someone read the log.
    await AuditService(session).record(
        AuditAction.REPORT_EXPORTED,
        entity_type="AUDIT_LOG",
        after={"filters": applied or "none"},
        detail=(
            "Exported the audit trail as CSV"
            + (f" (filters: {applied})" if applied else " (no filters).")
        ),
    )

    query = service.apply_filters(
        service.base_query(),
        action=action,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
    )
    stamp = clock.now().strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        service.stream_csv(query),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="tps-audit-{stamp}.csv"'},
    )


@router.get(
    "/entity/{entity_type}/{entity_id}",
    summary="Everything that happened to one record",
    description=(
        "One allocation's whole history in the order it happened — approved, offered, "
        "declined, promoted, accepted, conducted, evaluated.\n\n"
        "This is what makes a decision reviewable a year later. Readable by Training "
        "Administrators as well as System Administrators, because the person who has "
        "to explain a decision is usually the one who took it."
    ),
    response_model=list[AuditEntryRead],
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "The record's history, oldest first."}},
)
async def entity_history(
    entity_type: str, entity_id: int, user: CurrentUser, service: ServiceDep
) -> list[AuditEntryRead]:
    """Return the audit history of one record."""
    _ = user
    return await service.for_entity(entity_type.upper(), entity_id)
