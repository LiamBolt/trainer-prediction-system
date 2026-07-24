"""Report routes (FR-11, §6.9).

PDF generation stays on the frontend, which already has the UPF letterhead. These
endpoints return clean JSON plus the filters that produced it, so the exported PDF can
state its own provenance.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import ClockDep, CurrentUser, DbSession, require_roles
from app.core.exceptions import NotFoundError
from app.models.enums import AuditAction, RoleName
from app.schemas.dashboard import ReportResponse
from app.services.audit_service import AuditService
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])

TA = RoleName.TRAINING_ADMINISTRATOR
SA = RoleName.SYSTEM_ADMINISTRATOR

#: CSV columns per report type.
EXPORT_COLUMNS = {
    "utilisation": (
        "trainer_id",
        "trainer_name",
        "rank",
        "force_number",
        "station",
        "allocations",
        "last_assigned",
        "mean_score",
    ),
    "allocation-history": (
        "registry_number",
        "programme_title",
        "trainer_name",
        "approved_by_name",
        "approval_date",
        "status",
        "score",
        "evaluation_score",
    ),
}


def get_service(session: DbSession, clock: ClockDep) -> ReportService:
    """Construct the report service."""
    return ReportService(session, clock)


ServiceDep = Annotated[ReportService, Depends(get_service)]

DateFrom = Annotated[datetime.date | None, Query(alias="from")]
DateTo = Annotated[datetime.date | None, Query(alias="to")]


@router.get(
    "/utilisation",
    summary="Allocations per trainer (FR-11)",
    description=(
        "**This is the report that holds the system to account.** A ranking engine "
        "that keeps surfacing the same six names is working exactly as designed and "
        "failing at the purpose, and this is where that becomes visible.\n\n"
        "Trainers with **no** allocations are included deliberately — an empty row is "
        "the finding. A report listing only busy people cannot show who is never used.\n\n"
        "`region` filters on the **trainer's posting**, not the course venue: the "
        "question is which postings are being drawn on, not where courses ran."
    ),
    response_model=ReportResponse,
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "Rows, a chart of the busiest ten, and the filters used."}},
)
async def utilisation(
    user: CurrentUser,
    service: ServiceDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    region_id: Annotated[int | None, Query(alias="region")] = None,
) -> ReportResponse:
    """Return the utilisation report."""
    _ = user
    return await service.utilisation(
        date_from=date_from, date_to=date_to, category_id=category_id, region_id=region_id
    )


@router.get(
    "/allocation-history",
    summary="Allocations with their outcomes (FR-11)",
    description="Who was assigned to what, by whom, and what came of it.",
    response_model=ReportResponse,
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "Rows, a chart by outcome, and the filters used."}},
)
async def allocation_history(
    user: CurrentUser,
    service: ServiceDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    allocation_status: Annotated[str | None, Query(alias="status")] = None,
) -> ReportResponse:
    """Return the allocation-history report."""
    _ = user
    return await service.allocation_history(
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        status=allocation_status,
    )


@router.get(
    "/performance-trends",
    summary="Mean evaluation score by quarter (FR-11)",
    description=(
        "Is delivery getting better or worse? Filterable by category and "
        "specialisation.\n\n"
        "These are **raw** means, not the shrunk figures the prediction engine uses. "
        "A quarter's mean is a description of what happened; the engine's shrinkage "
        "exists to stop a single evaluation dominating a *ranking*, which is a "
        "different job."
    ),
    response_model=ReportResponse,
    dependencies=[Depends(require_roles(TA, SA))],
    responses={200: {"description": "One row per quarter, oldest first."}},
)
async def performance_trends(
    user: CurrentUser,
    service: ServiceDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    specialization_area_id: Annotated[int | None, Query(alias="specializationAreaId")] = None,
) -> ReportResponse:
    """Return the performance-trend report."""
    _ = user
    return await service.performance_trends(
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        specialization_area_id=specialization_area_id,
    )


@router.get(
    "/{report_type}/export",
    summary="Export a report as CSV",
    description=(
        "Server-side CSV via `StreamingResponse` — the file is never materialised in "
        "memory. `reportType` is `utilisation` or `allocation-history`.\n\n"
        "The export is audited as `REPORT_EXPORTED`, with the filters that produced it."
    ),
    dependencies=[Depends(require_roles(TA, SA))],
    responses={
        200: {
            "description": "A CSV stream.",
            "content": {"text/csv": {"schema": {"type": "string"}}},
        },
        404: {"description": "Unknown report type."},
    },
)
async def export_report(
    report_type: str,
    session: DbSession,
    user: CurrentUser,
    service: ServiceDep,
    clock: ClockDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    export_format: Annotated[str, Query(alias="format")] = "csv",
) -> StreamingResponse:
    """Stream a report as CSV.

    Raises:
        NotFoundError: If the report type or format is not one this endpoint serves.
    """
    _ = user
    if export_format.lower() != "csv":
        raise NotFoundError(
            f"'{export_format}' is not an export format here. This endpoint streams CSV; "
            "PDF is generated by the frontend, which holds the UPF letterhead."
        )
    if report_type not in EXPORT_COLUMNS:
        available = ", ".join(sorted(EXPORT_COLUMNS))
        raise NotFoundError(f"'{report_type}' is not a report. Available: {available}.")

    if report_type == "utilisation":
        query = service.utilisation_query(
            date_from=date_from, date_to=date_to, category_id=category_id
        )
    else:
        query = service.allocation_history_query(
            date_from=date_from, date_to=date_to, category_id=category_id
        )

    filters = {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "category": category_id,
    }
    applied = {k: v for k, v in filters.items() if v is not None}
    await AuditService(session).record(
        AuditAction.REPORT_EXPORTED,
        entity_type="REPORT",
        after={"report": report_type, "filters": applied or "none"},
        detail=f"Exported the {report_type} report as CSV.",
    )

    stamp = clock.now().strftime("%Y%m%d-%H%M")
    return StreamingResponse(
        service.stream_csv(query, EXPORT_COLUMNS[report_type]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="tps-{report_type}-{stamp}.csv"'
        },
    )


# --- Group A aliases (A4, A5) ------------------------------------------------
# The frontend calls `/reports/allocations` and `/reports/performance`.


@router.get("/allocations", response_model=ReportResponse, include_in_schema=False)
async def allocation_history_alias(
    user: CurrentUser,
    service: ServiceDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    allocation_status: Annotated[str | None, Query(alias="status")] = None,
) -> ReportResponse:
    """Alias of `GET /reports/allocation-history`."""
    return await allocation_history(
        user, service, date_from, date_to, category_id, allocation_status
    )


@router.get("/performance", response_model=ReportResponse, include_in_schema=False)
async def performance_alias(
    user: CurrentUser,
    service: ServiceDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    category_id: Annotated[int | None, Query(alias="category")] = None,
    specialization_area_id: Annotated[int | None, Query(alias="specializationAreaId")] = None,
) -> ReportResponse:
    """Alias of `GET /reports/performance-trends`."""
    return await performance_trends(
        user, service, date_from, date_to, category_id, specialization_area_id
    )
