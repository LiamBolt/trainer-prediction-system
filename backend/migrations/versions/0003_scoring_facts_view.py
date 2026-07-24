"""The ``v_trainer_scoring_facts`` read view (§5.10).

Pre-aggregates, per trainer, everything the prediction engine needs from history:
evaluation depth, mean rating, recency, per-discipline breakdowns, current workload,
and the date of the last assignment.

**A plain VIEW, not a materialized view.** At 812 trainers the aggregation is
milliseconds, and a plain view is always current. A materialized view would let an
evaluation recorded five minutes ago fail to influence the next prediction run, which
breaks the SRS feedback loop — the loop is the point of FR-10. Revisit with
``REFRESH MATERIALIZED VIEW CONCURRENTLY`` if the trainer population passes roughly
50,000; see ADR-0007.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Allocation statuses that count as occupying a trainer right now. A DECLINED or
#: WITHDRAWN allocation consumes no capacity; an EVALUATED one is finished.
ACTIVE_ALLOCATION_STATUSES = "('PENDING_TRAINER', 'CONFIRMED', 'CONDUCTED')"

VIEW_SQL = f"""
CREATE VIEW v_trainer_scoring_facts AS
SELECT
    t.trainer_id,

    -- Evaluation depth and quality. Scalar subqueries rather than joined aggregates:
    -- joining evaluations and allocations in one GROUP BY fans out the rows and
    -- silently multiplies both counts.
    COALESCE(ev.evaluation_count, 0)            AS evaluation_count,
    ev.mean_score_awarded                       AS mean_score_awarded,
    ev.last_evaluation_date                     AS last_evaluation_date,

    -- Per-discipline breakdown, keyed by specialization_areas.discipline_group.
    -- The PERFORMANCE criterion needs "how many of this trainer's evaluations were
    -- in the group this programme belongs to?", which is a different question per
    -- programme. Returning a JSONB map keeps the view one row per trainer while
    -- still answering it in a single lookup, instead of forcing the grain to
    -- trainer x group and making every consumer re-aggregate.
    COALESCE(ev.evaluations_by_group, '{{}}'::jsonb)  AS evaluations_by_discipline_group,
    COALESCE(ev.mean_by_group, '{{}}'::jsonb)         AS mean_by_discipline_group,

    -- Current workload, feeding the AVAILABILITY criterion.
    COALESCE(al.active_allocation_count, 0)     AS active_allocation_count,
    al.last_assignment_date                     AS last_assignment_date,
    COALESCE(al.total_allocation_count, 0)      AS total_allocation_count,

    -- Profile depth, feeding the confidence level.
    COALESCE(q.qualification_count, 0)          AS qualification_count,
    COALESCE(s.specialization_count, 0)         AS specialization_count,
    t.profile_completeness                      AS profile_completeness

FROM trainers t

LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                        AS evaluation_count,
        ROUND(AVG(e.score_awarded), 2)  AS mean_score_awarded,
        MAX(e.evaluation_date)          AS last_evaluation_date,
        jsonb_object_agg(g.discipline_group, g.group_count)
            FILTER (WHERE g.discipline_group IS NOT NULL)  AS evaluations_by_group,
        jsonb_object_agg(g.discipline_group, g.group_mean)
            FILTER (WHERE g.discipline_group IS NOT NULL)  AS mean_by_group
    FROM performance_evaluations e
    LEFT JOIN LATERAL (
        SELECT
            sa.discipline_group,
            COUNT(*) OVER (PARTITION BY sa.discipline_group)                        AS group_count,
            ROUND(AVG(e2.score_awarded) OVER (PARTITION BY sa.discipline_group), 2) AS group_mean
        FROM performance_evaluations e2
        JOIN training_programmes p2 ON p2.programme_id = e2.programme_id
        LEFT JOIN specialization_areas sa
               ON sa.specialization_area_id = p2.required_specialization_area_id
        WHERE e2.trainer_id = e.trainer_id
          AND e2.evaluation_id = e.evaluation_id
    ) g ON TRUE
    WHERE e.trainer_id = t.trainer_id
) ev ON TRUE

LEFT JOIN LATERAL (
    SELECT
        COUNT(*) FILTER (WHERE a.status IN {ACTIVE_ALLOCATION_STATUSES}) AS active_allocation_count,
        COUNT(*)                                                          AS total_allocation_count,
        MAX(a.approval_date)                                              AS last_assignment_date
    FROM allocations a
    WHERE a.trainer_id = t.trainer_id
) al ON TRUE

LEFT JOIN LATERAL (
    SELECT COUNT(*) AS qualification_count
    FROM trainer_qualifications tq
    WHERE tq.trainer_id = t.trainer_id
) q ON TRUE

LEFT JOIN LATERAL (
    SELECT COUNT(*) AS specialization_count
    FROM trainer_specializations ts
    WHERE ts.trainer_id = t.trainer_id
) s ON TRUE;
"""


def upgrade() -> None:
    """Create the view and document it in ``pg_description``."""
    op.execute(VIEW_SQL)
    op.execute(
        "COMMENT ON VIEW v_trainer_scoring_facts IS "
        "'Per-trainer scoring facts: evaluation depth, mean rating, per-discipline "
        "breakdown, current workload, and profile depth. A plain view, so a "
        "just-recorded evaluation influences the very next prediction (ADR-0007).';"
    )


def downgrade() -> None:
    """Drop the view."""
    op.execute("DROP VIEW IF EXISTS v_trainer_scoring_facts;")
