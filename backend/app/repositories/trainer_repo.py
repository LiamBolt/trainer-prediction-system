"""Trainer queries, including the prediction engine's facts query (§5.2).

The facts query is the performance-critical path in this system. It must be **one
round trip** producing one row per trainer — never 812 ORM entities with relationships,
which in async SQLAlchemy would either N+1 or raise ``MissingGreenlet``.

It is written as ``text()`` with bound parameters rather than assembled from Core
constructs. Six correlated ``LATERAL`` subqueries expressed through the ORM layer would
be materially harder to read and to reason about against an ``EXPLAIN`` plan, and the
plan is the thing that matters here. Every value is bound; nothing is interpolated.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User
from app.models.reference import Directorate, PoliceRank, Region, Station
from app.models.trainer import Trainer, TrainerSpecialization
from app.services.prediction.types import CandidateFacts, ScheduleConflict

#: Allocation statuses that occupy a trainer for scheduling purposes. A DECLINED or
#: WITHDRAWN allocation consumes nothing; an EVALUATED one is finished.
OCCUPYING_STATUSES = ("PENDING_TRAINER", "CONFIRMED", "CONDUCTED")

#: One row per trainer, everything the engine needs (§5.2). **One round trip.**
#:
#: Structure: eight pre-aggregated CTEs, each scanning its table **once**, hash-joined
#: onto the trainer rows.
#:
#: The obvious shape — a correlated ``LATERAL`` per fact — was measured first and was
#: three times too slow: eight subqueries times 812 trainers is 6,496 nested-loop
#: iterations, and it spent 399 ms of a 150 ms budget inside PostgreSQL. Aggregating
#: set-wise and joining once is the same result with a fraction of the work.
#:
#: Separate CTEs rather than one grouped query because joining qualifications,
#: specialisations, allocations and evaluations together fans the rows out and silently
#: multiplies every count by the others' cardinality.
FACTS_SQL = text(
    f"""
WITH area_programmes AS MATERIALIZED (
    -- Programmes belonging to this discipline group, resolved once rather than
    -- re-joined per trainer.
    SELECT p.programme_id
    FROM training_programmes p
    JOIN specialization_areas sa
      ON sa.specialization_area_id = p.required_specialization_area_id
    WHERE CAST(:discipline_group AS text) IS NOT NULL
      AND sa.discipline_group = CAST(:discipline_group AS text)
),
eval_totals AS MATERIALIZED (
    SELECT e.trainer_id,
           COUNT(*)               AS evaluation_count,
           AVG(e.score_awarded)   AS evaluation_mean,
           MAX(e.evaluation_date) AS last_evaluation_date
    FROM performance_evaluations e
    GROUP BY e.trainer_id
),
eval_in_area AS MATERIALIZED (
    SELECT e.trainer_id,
           COUNT(*)             AS evaluation_count_in_area,
           AVG(e.score_awarded) AS evaluation_mean_in_area
    FROM performance_evaluations e
    WHERE e.programme_id IN (SELECT programme_id FROM area_programmes)
    GROUP BY e.trainer_id
),
workload AS MATERIALIZED (
    SELECT a.trainer_id,
           COUNT(*) FILTER (WHERE a.status IN {OCCUPYING_STATUSES!r})
                                      AS active_allocation_count,
           MAX(a.approval_date)::date AS last_assigned_date
    FROM allocations a
    GROUP BY a.trainer_id
),
highest_qualification AS MATERIALIZED (
    -- DISTINCT ON is PostgreSQL's idiom for "the best row per group"; it beats a
    -- window function here because only one row per trainer survives.
    SELECT DISTINCT ON (tq.trainer_id)
           tq.trainer_id, ql.score_value, ql.rank_order, ql.name
    FROM trainer_qualifications tq
    JOIN qualification_levels ql ON ql.level_id = tq.level_id
    ORDER BY tq.trainer_id, ql.rank_order DESC
),
police_qualification AS MATERIALIZED (
    -- Driven by institutions.institution_type, not by matching institution names, so
    -- a newly added police school earns the bonus without a code change.
    SELECT DISTINCT tq.trainer_id
    FROM trainer_qualifications tq
    JOIN institutions i ON i.institution_id = tq.institution_id
    WHERE i.institution_type = 'POLICE'
),
required_proficiency AS MATERIALIZED (
    SELECT ts.trainer_id, pl.score_value, pl.name
    FROM trainer_specializations ts
    JOIN proficiency_levels pl ON pl.level_id = ts.proficiency_level_id
    WHERE ts.specialization_area_id = CAST(:area_id AS bigint)
),
group_breadth AS MATERIALIZED (
    -- A *second* specialisation in the same discipline group, earning the breadth bonus.
    SELECT DISTINCT ts.trainer_id
    FROM trainer_specializations ts
    JOIN specialization_areas sa
      ON sa.specialization_area_id = ts.specialization_area_id
    WHERE ts.specialization_area_id <> CAST(:area_id AS bigint)
      AND CAST(:discipline_group AS text) IS NOT NULL
      AND sa.discipline_group = CAST(:discipline_group AS text)
),
conflicts AS MATERIALIZED (
    -- The nearest commitment clashing with these dates: an occupied allocation or a
    -- declared absence. DISTINCT ON keeps the earliest per trainer, so the exclusion
    -- message names the clash an officer will recognise first.
    SELECT DISTINCT ON (c.trainer_id)
           c.trainer_id, c.title, c.start_date, c.end_date, c.kind
    FROM (
        SELECT a.trainer_id, p.title, p.start_date, p.end_date, 'ALLOCATION' AS kind
        FROM allocations a
        JOIN training_programmes p ON p.programme_id = a.programme_id
        WHERE a.status IN {OCCUPYING_STATUSES!r}
          AND a.programme_id <> CAST(:programme_id AS bigint)
          AND p.start_date <= CAST(:end_date AS date)
          AND p.end_date   >= CAST(:start_date AS date)
        UNION ALL
        SELECT tu.trainer_id, tu.reason, tu.start_date, tu.end_date, 'UNAVAILABILITY'
        FROM trainer_unavailability tu
        WHERE tu.start_date <= CAST(:end_date AS date)
          AND tu.end_date   >= CAST(:start_date AS date)
    ) c
    ORDER BY c.trainer_id, c.start_date
)
SELECT
    t.trainer_id,
    u.full_name,
    r.code                              AS rank_code,
    t.force_number,
    s.name                              AS station_name,
    t.years_experience,
    t.availability_status,
    t.profile_completeness,

    hq.score_value                      AS highest_qualification_score,
    hq.rank_order                        AS highest_qualification_order,
    hq.name                              AS highest_qualification_name,
    (pq.trainer_id IS NOT NULL)          AS has_police_institution_qualification,

    rp.score_value                       AS proficiency_score_in_required_area,
    rp.name                              AS proficiency_name_in_required_area,
    (gb.trainer_id IS NOT NULL)          AS has_group_matching_specialisation,

    COALESCE(et.evaluation_count, 0)     AS evaluation_count,
    et.evaluation_mean,
    COALESCE(ea.evaluation_count_in_area, 0) AS evaluation_count_in_area,
    ea.evaluation_mean_in_area,
    et.last_evaluation_date,
    COALESCE(w.active_allocation_count, 0) AS active_allocation_count,
    w.last_assigned_date,

    cf.title                             AS conflict_title,
    cf.start_date                        AS conflict_start,
    cf.end_date                          AS conflict_end,
    cf.kind                              AS conflict_kind

FROM trainers t
JOIN users        u ON u.user_id    = t.user_id
JOIN police_ranks r ON r.rank_id    = t.rank_id
JOIN stations     s ON s.station_id = t.station_id
LEFT JOIN highest_qualification hq ON hq.trainer_id = t.trainer_id
LEFT JOIN police_qualification  pq ON pq.trainer_id = t.trainer_id
LEFT JOIN required_proficiency  rp ON rp.trainer_id = t.trainer_id
LEFT JOIN group_breadth         gb ON gb.trainer_id = t.trainer_id
LEFT JOIN eval_totals           et ON et.trainer_id = t.trainer_id
LEFT JOIN eval_in_area          ea ON ea.trainer_id = t.trainer_id
LEFT JOIN workload              w  ON w.trainer_id  = t.trainer_id
LEFT JOIN conflicts             cf ON cf.trainer_id = t.trainer_id
-- NULL means "the whole pool", which is the prediction case. A non-empty array narrows
-- to specific trainers, which is how an approval re-checks the gates against live data
-- without a second, hand-written copy of the same rules. The CAST is required: asyncpg
-- cannot infer a parameter's type from `IS NULL` alone.
WHERE CAST(:trainer_ids AS bigint[]) IS NULL
   OR t.trainer_id = ANY(CAST(:trainer_ids AS bigint[]))
"""
)


class TrainerRepository:
    """Queries over trainers.

    Args:
        session: The request's session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_scoring_facts(
        self,
        *,
        area_id: int,
        discipline_group: str | None,
        programme_id: int,
        start_date: datetime.date,
        end_date: datetime.date,
        trainer_ids: Sequence[int] | None = None,
    ) -> list[CandidateFacts]:
        """Project every trainer into :class:`CandidateFacts` in one round trip (§5.2).

        Returns the **whole pool**, including trainers who will be gated out.
        Exclusion is the engine's decision, not this query's, so that the Exclusion
        Ledger can report on everyone rather than only on those who nearly qualified.

        Args:
            area_id: The programme's required specialisation area.
            discipline_group: Its subject grouping, for the breadth bonus and the
                evaluation relevance test. May be None.
            programme_id: The programme being staffed. Excluded from the conflict
                search so a re-run does not report a trainer as clashing with the very
                course they are being considered for.
            start_date: Course start, for the conflict window.
            end_date: Course end.
            trainer_ids: Narrow to specific trainers. ``None`` returns the whole pool,
                which is what a prediction run wants. An approval passes a single id to
                re-check the gates against live data using **this** query rather than a
                second implementation of the same rules — two copies of a business rule
                is how an approval starts admitting someone the ranking excluded.

        Returns:
            One :class:`CandidateFacts` per trainer.
        """
        result = await self._session.execute(
            FACTS_SQL,
            {
                "area_id": area_id,
                "discipline_group": discipline_group,
                "programme_id": programme_id,
                "start_date": start_date,
                "end_date": end_date,
                "trainer_ids": list(trainer_ids) if trainer_ids is not None else None,
            },
        )
        return [_to_facts(row) for row in result.mappings()]

    async def prior_mean(self) -> Decimal | None:
        """Return the mean of every evaluation in the system (§5.5).

        The shrinkage prior. Recomputed per run rather than stored, because it moves
        as evaluations accumulate — and a run stores the value it used, so an old
        prediction stays reproducible against the prior that produced it.

        Returns:
            The mean, or None when the system holds no evaluations at all.
        """
        result = await self._session.execute(
            text("SELECT AVG(score_awarded) FROM performance_evaluations")
        )
        value = result.scalar_one_or_none()
        return Decimal(str(value)) if value is not None else None

    def directory_query(self) -> Select[Any]:
        """Build the base projection for the trainer directory (§6.3).

        A projection, not entity hydration: the directory shows twelve columns and
        never touches a relationship, so loading 812 ORM objects with their
        qualifications would fetch several thousand rows to display a table.

        Returns:
            A ``SELECT`` ready for filtering, sorting, and pagination.
        """
        return (
            select(
                Trainer.trainer_id,
                Trainer.user_id,
                User.full_name,
                Trainer.force_number,
                PoliceRank.code.label("police_rank"),
                Station.name.label("station"),
                Region.name.label("region"),
                Directorate.name.label("directorate"),
                Trainer.years_experience,
                Trainer.availability_status,
                Trainer.contact_number,
                Trainer.profile_completeness,
            )
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .join(Station, Station.station_id == Trainer.station_id)
            .join(Region, Region.region_id == Station.region_id)
            .join(Directorate, Directorate.directorate_id == Trainer.directorate_id)
        )

    @staticmethod
    def apply_directory_filters(
        query: Select[Any],
        *,
        search: str | None = None,
        specialization_area_id: int | None = None,
        proficiency_level_id: int | None = None,
        station_id: int | None = None,
        region_id: int | None = None,
        directorate_id: int | None = None,
        availability_status: str | None = None,
        min_experience: int | None = None,
        max_experience: int | None = None,
    ) -> Select[Any]:
        """Apply directory filters to a query.

        ``search`` matches name or force number. It uses ``ILIKE`` with wildcards,
        which the GIN trigram indexes on ``searchable_name`` and ``force_number``
        serve — an ordinary B-tree cannot answer a leading-wildcard match.

        Args:
            query: The base query.
            search: Free text over name and force number.
            specialization_area_id: Restrict to holders of a discipline.
            proficiency_level_id: Combined with the above, restrict by level.
            station_id: Posting.
            region_id: Region of posting.
            directorate_id: Directorate.
            availability_status: Availability.
            min_experience: Inclusive lower bound on years.
            max_experience: Inclusive upper bound.

        Returns:
            The filtered query.
        """
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(Trainer.searchable_name.ilike(pattern), Trainer.force_number.ilike(pattern))
            )
        if specialization_area_id is not None:
            exists = select(TrainerSpecialization.specialization_id).where(
                TrainerSpecialization.trainer_id == Trainer.trainer_id,
                TrainerSpecialization.specialization_area_id == specialization_area_id,
            )
            if proficiency_level_id is not None:
                exists = exists.where(
                    TrainerSpecialization.proficiency_level_id == proficiency_level_id
                )
            query = query.where(exists.exists())
        if station_id is not None:
            query = query.where(Trainer.station_id == station_id)
        if region_id is not None:
            query = query.where(Station.region_id == region_id)
        if directorate_id is not None:
            query = query.where(Trainer.directorate_id == directorate_id)
        if availability_status is not None:
            query = query.where(Trainer.availability_status == availability_status)
        if min_experience is not None:
            query = query.where(Trainer.years_experience >= min_experience)
        if max_experience is not None:
            query = query.where(Trainer.years_experience <= max_experience)
        return query

    async def count(self, query: Select[Any]) -> int:
        """Count the rows a filtered query would return.

        Args:
            query: The filtered query, before pagination.

        Returns:
            The total row count.
        """
        result = await self._session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        return int(result.scalar_one())

    async def get_by_id(self, trainer_id: int) -> Row[Any] | None:
        """Fetch one trainer's directory row.

        Args:
            trainer_id: Primary key.

        Returns:
            The row, or None.
        """
        result = await self._session.execute(
            self.directory_query().where(Trainer.trainer_id == trainer_id)
        )
        return result.one_or_none()

    async def get_by_user_id(self, user_id: int) -> Row[Any] | None:
        """Fetch the trainer linked to a user account.

        Args:
            user_id: The user's primary key.

        Returns:
            The row, or None when the user is not a trainer.
        """
        result = await self._session.execute(
            self.directory_query().where(Trainer.user_id == user_id)
        )
        return result.one_or_none()


def _to_facts(row: Any) -> CandidateFacts:
    """Convert one facts row into the engine's input type.

    Args:
        row: A mapping from the facts query.

    Returns:
        The candidate facts.
    """
    conflict: ScheduleConflict | None = None
    if row["conflict_title"] is not None:
        conflict = ScheduleConflict(
            title=row["conflict_title"],
            start_date=row["conflict_start"],
            end_date=row["conflict_end"],
            kind=row["conflict_kind"],
        )

    return CandidateFacts(
        trainer_id=row["trainer_id"],
        full_name=row["full_name"],
        rank_code=row["rank_code"],
        force_number=row["force_number"],
        station_name=row["station_name"],
        years_experience=row["years_experience"],
        availability_status=row["availability_status"],
        highest_qualification_score=row["highest_qualification_score"],
        highest_qualification_order=row["highest_qualification_order"],
        highest_qualification_name=row["highest_qualification_name"],
        has_police_institution_qualification=row["has_police_institution_qualification"],
        proficiency_score_in_required_area=row["proficiency_score_in_required_area"],
        proficiency_name_in_required_area=row["proficiency_name_in_required_area"],
        has_group_matching_specialisation=row["has_group_matching_specialisation"],
        evaluation_count=row["evaluation_count"],
        evaluation_mean=row["evaluation_mean"],
        evaluation_count_in_area=row["evaluation_count_in_area"],
        evaluation_mean_in_area=row["evaluation_mean_in_area"],
        last_evaluation_date=row["last_evaluation_date"],
        active_allocation_count=row["active_allocation_count"],
        last_assigned_date=row["last_assigned_date"],
        profile_completeness=row["profile_completeness"],
        conflict=conflict,
    )
