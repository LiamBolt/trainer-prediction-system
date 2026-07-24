"""Reports (FR-11, §6.9). Imports no `fastapi` (B7).

Three reports, each answering a question somebody actually asks:

- **Utilisation** — "are we leaning on the same six people?" This is the report that
  holds the system to account. A ranking engine that always surfaces the same names is
  working exactly as designed and failing at the purpose, and this is where that shows.
- **Allocation history** — "who was assigned to what, by whom, and what came of it?"
- **Performance trends** — "is delivery getting better or worse?"

Every response carries the filters that produced it, so an exported PDF can state its
own provenance. Figures without their filters is how two people end up arguing about
numbers that were never comparable.

CSV export streams. A report over five years of history does not fit in the memory of
a container sized for a web API.
"""

from __future__ import annotations

import csv
import datetime
import io
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any

from pydantic.alias_generators import to_camel
from sqlalchemy import Integer, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.identity import User
from app.models.programme import TrainingProgramme
from app.models.reference import PoliceRank, Station
from app.models.trainer import Trainer
from app.schemas.dashboard import (
    AllocationHistoryRow,
    PerformanceTrendRow,
    ReportResponse,
    TrendPoint,
    UtilisationRow,
)

#: Rows a JSON report returns before the caller is pointed at the CSV export. A report
#: that returns 40,000 rows to a browser is a download pretending to be a page.
MAX_REPORT_ROWS = 5_000


class ReportService:
    """Builds the three FR-11 reports.

    Args:
        session: The request's session.
        clock: Injected clock, for `generatedAt`.
    """

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    # ------------------------------------------------------- utilisation

    def utilisation_query(
        self,
        *,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        category_id: int | None = None,
        region_id: int | None = None,
    ) -> Select[Any]:
        """Build the utilisation query (§6.9).

        Counts allocations per trainer over a period. Trainers with **no** allocations
        are included deliberately — an empty row is the finding. A report that lists
        only the busy people cannot show you who is never used.

        Args:
            date_from: Allocations approved on or after.
            date_to: Allocations approved on or before.
            category_id: Restrict to one training category.
            region_id: Restrict to trainers posted in one region.

        Returns:
            The query.
        """
        conditions = [Allocation.trainer_id == Trainer.trainer_id]
        if date_from is not None:
            conditions.append(Allocation.approval_date >= date_from)
        if date_to is not None:
            conditions.append(Allocation.approval_date < date_to + datetime.timedelta(days=1))
        if category_id is not None:
            conditions.append(
                Allocation.programme_id.in_(
                    select(TrainingProgramme.programme_id).where(
                        TrainingProgramme.category_id == category_id
                    )
                )
            )

        allocation_count = (
            select(func.count())
            .select_from(Allocation)
            .where(*conditions)
            .scalar_subquery()
            .label("allocations")
        )
        last_assigned = (
            select(func.max(Allocation.approval_date))
            .select_from(Allocation)
            .where(*conditions)
            .scalar_subquery()
            .label("last_assigned")
        )
        mean_score = (
            select(func.round(func.avg(PerformanceEvaluation.score_awarded), 2))
            .select_from(PerformanceEvaluation)
            .where(PerformanceEvaluation.trainer_id == Trainer.trainer_id)
            .scalar_subquery()
            .label("mean_score")
        )

        query = (
            select(
                Trainer.trainer_id,
                User.full_name.label("trainer_name"),
                PoliceRank.code.label("rank"),
                Trainer.force_number,
                Station.name.label("station"),
                allocation_count,
                last_assigned,
                mean_score,
            )
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .join(Station, Station.station_id == Trainer.station_id)
        )
        if region_id is not None:
            query = query.where(Station.region_id == region_id)
        return query.order_by(allocation_count.desc(), User.full_name)

    async def utilisation(self, **filters: Any) -> ReportResponse:
        """Run the utilisation report.

        Args:
            **filters: Passed to :meth:`utilisation_query`.

        Returns:
            Rows, a chart of the busiest ten, and the filters used.
        """
        result = await self._session.execute(
            self.utilisation_query(**filters).limit(MAX_REPORT_ROWS)
        )
        rows = [UtilisationRow.model_validate(row) for row in result.all()]
        chart = [
            TrendPoint(label=f"{row.rank} {row.trainer_name}", value=float(row.allocations))
            for row in rows[:10]
        ]
        return self._respond(rows, chart, filters)

    # -------------------------------------------------- allocation history

    def allocation_history_query(
        self,
        *,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        category_id: int | None = None,
        status: str | None = None,
    ) -> Select[Any]:
        """Build the allocation-history query (§6.9).

        Args:
            date_from: Approved on or after.
            date_to: Approved on or before.
            category_id: One training category.
            status: One allocation status.

        Returns:
            The query.
        """
        approver = User.__table__.alias("approver")
        trainer_user = User.__table__.alias("trainer_user")

        query = (
            select(
                Allocation.allocation_id,
                Allocation.registry_number,
                TrainingProgramme.title.label("programme_title"),
                trainer_user.c.full_name.label("trainer_name"),
                approver.c.full_name.label("approved_by_name"),
                Allocation.approval_date,
                Allocation.status,
                Allocation.frozen_score.label("score"),
                PerformanceEvaluation.score_awarded.label("evaluation_score"),
            )
            .join(TrainingProgramme, TrainingProgramme.programme_id == Allocation.programme_id)
            .join(Trainer, Trainer.trainer_id == Allocation.trainer_id)
            .join(trainer_user, trainer_user.c.user_id == Trainer.user_id)
            .join(approver, approver.c.user_id == Allocation.approved_by_user_id)
            .outerjoin(
                PerformanceEvaluation,
                PerformanceEvaluation.allocation_id == Allocation.allocation_id,
            )
        )
        if date_from is not None:
            query = query.where(Allocation.approval_date >= date_from)
        if date_to is not None:
            query = query.where(
                Allocation.approval_date < date_to + datetime.timedelta(days=1)
            )
        if category_id is not None:
            query = query.where(TrainingProgramme.category_id == category_id)
        if status:
            query = query.where(Allocation.status == status)
        return query.order_by(Allocation.approval_date.desc())

    async def allocation_history(self, **filters: Any) -> ReportResponse:
        """Run the allocation-history report.

        Args:
            **filters: Passed to :meth:`allocation_history_query`.

        Returns:
            Rows, a chart of allocations by outcome, and the filters used.
        """
        result = await self._session.execute(
            self.allocation_history_query(**filters).limit(MAX_REPORT_ROWS)
        )
        rows = [AllocationHistoryRow.model_validate(row) for row in result.all()]
        by_status: dict[str, int] = {}
        for row in rows:
            by_status[row.status] = by_status.get(row.status, 0) + 1
        chart = [
            TrendPoint(label=status, value=float(count))
            for status, count in sorted(by_status.items(), key=lambda kv: -kv[1])
        ]
        return self._respond(rows, chart, filters)

    # -------------------------------------------------- performance trends

    async def performance_trends(
        self,
        *,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        category_id: int | None = None,
        specialization_area_id: int | None = None,
    ) -> ReportResponse:
        """Mean evaluation score by quarter (§6.9).

        Args:
            date_from: Evaluated on or after.
            date_to: Evaluated on or before.
            category_id: One training category.
            specialization_area_id: One discipline.

        Returns:
            One row per quarter, oldest first.
        """
        quarter = func.concat(
            cast(func.extract("year", PerformanceEvaluation.evaluation_date), Integer),
            " Q",
            cast(func.extract("quarter", PerformanceEvaluation.evaluation_date), Integer),
        )
        query = (
            select(
                quarter.label("quarter"),
                func.round(func.avg(PerformanceEvaluation.score_awarded), 2).label("mean_score"),
                func.count().label("evaluation_count"),
                func.min(PerformanceEvaluation.evaluation_date).label("sort_key"),
            )
            .join(
                TrainingProgramme,
                TrainingProgramme.programme_id == PerformanceEvaluation.programme_id,
            )
            .group_by(quarter)
            .order_by(func.min(PerformanceEvaluation.evaluation_date))
        )
        if date_from is not None:
            query = query.where(PerformanceEvaluation.evaluation_date >= date_from)
        if date_to is not None:
            query = query.where(PerformanceEvaluation.evaluation_date <= date_to)
        if category_id is not None:
            query = query.where(TrainingProgramme.category_id == category_id)
        if specialization_area_id is not None:
            query = query.where(
                TrainingProgramme.required_specialization_area_id == specialization_area_id
            )

        result = await self._session.execute(query)
        rows = [PerformanceTrendRow.model_validate(row) for row in result.all()]
        chart = [
            TrendPoint(label=row.quarter, value=float(row.mean_score or Decimal("0")))
            for row in rows
        ]
        filters = {
            "date_from": date_from,
            "date_to": date_to,
            "category_id": category_id,
            "specialization_area_id": specialization_area_id,
        }
        return self._respond(rows, chart, filters)

    # ------------------------------------------------------------- export

    async def stream_csv(
        self, query: Select[Any], columns: Sequence[str], *, chunk: int = 1000
    ) -> AsyncIterator[str]:
        """Stream a report as CSV (§6.9).

        Args:
            query: The report query.
            columns: Column names, in order.
            chunk: Rows per round trip.

        Yields:
            CSV text, header first.
        """
        buffer = io.StringIO()
        csv.writer(buffer).writerow(columns)
        yield buffer.getvalue()

        offset = 0
        while True:
            result = await self._session.execute(query.offset(offset).limit(chunk))
            rows = result.all()
            if not rows:
                return
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            for row in rows:
                writer.writerow([getattr(row, column, "") for column in columns])
            yield buffer.getvalue()
            if len(rows) < chunk:
                return
            offset += chunk

    def _respond(
        self, rows: Sequence[Any], chart: list[TrendPoint], filters: dict[str, Any]
    ) -> ReportResponse:
        """Wrap rows with their provenance.

        Args:
            rows: The report rows.
            chart: Chart points.
            filters: What produced them.

        Returns:
            The response.
        """
        return ReportResponse(
            rows=list(rows),
            chart=chart,
            generated_at=self._clock.now(),
            # Camelised by hand: `filters` is a free-form dict, and Pydantic's alias
            # generator renames *fields*, not dictionary keys. Without this the echo
            # would go out as `date_from` while every other key in the API is
            # camelCase — B2 broken in the one place a client reads back its own input.
            filters={to_camel(k): v for k, v in filters.items() if v is not None},
            row_count=len(rows),
        )


def region_join_note() -> str:
    """Explain why utilisation filters region through the trainer's station.

    A trainer has a posting, not a region; the region comes from the station. Filtering
    on the *programme's* venue instead would answer a different question — "who taught
    in this region" rather than "who from this region is being used" — and the second is
    the one that exposes an under-used posting.

    Returns:
        The explanation, for the OpenAPI description.
    """
    return (
        "Region filters on the **trainer's posting**, not the course venue: the "
        "question is which postings are being drawn on, not where courses ran."
    )
