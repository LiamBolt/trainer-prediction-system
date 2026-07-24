"""Fix the per-discipline-group aggregates in v_trainer_scoring_facts.

Revision ID: 0004
Revises: 0003
Create Date: Phase 2, Stage 7

The view's `evaluations_by_discipline_group` and `mean_by_discipline_group` were wrong:
every group reported a count of 1, whatever the real figure.

The cause was a window function evaluated in the wrong scope. The inner `LATERAL` was
correlated to a **single** evaluation (`e2.evaluation_id = e.evaluation_id`), so
`count(*) OVER (PARTITION BY sa.discipline_group)` counted the rows visible *in that
one-row scope* — which is always one. `jsonb_object_agg` then dutifully aggregated a
column of 1s. The query was valid SQL, ran without complaint, and produced a plausible
shape, which is exactly why it survived review: the failure is invisible unless someone
checks a trainer they already know has six evaluations in one group.

The replacement aggregates set-wise: group the evaluations once with `GROUP BY`, then
build the JSONB from the grouped rows. No window functions, no nested correlation.

The prediction engine never depended on this — `TrainerRepository.FACTS_SQL` computes
its own per-group figures — but the dashboard, the reports, and anything else reading
the view did.
"""

from __future__ import annotations

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


#: The corrected view. Structure: four pre-aggregated CTEs joined onto trainers, the
#: same set-based shape the facts query settled on after the LATERAL version was
#: measured three times too slow.
CORRECTED_VIEW = """
CREATE OR REPLACE VIEW v_trainer_scoring_facts AS
WITH eval_totals AS (
    SELECT
        e.trainer_id,
        count(*)                          AS evaluation_count,
        round(avg(e.score_awarded), 2)    AS mean_score_awarded,
        max(e.evaluation_date)            AS last_evaluation_date
    FROM performance_evaluations e
    GROUP BY e.trainer_id
),
-- One row per (trainer, discipline group). This is the grouping the previous
-- definition never actually performed.
eval_per_group AS (
    SELECT
        e.trainer_id,
        sa.discipline_group,
        count(*)                          AS group_count,
        round(avg(e.score_awarded), 2)    AS group_mean
    FROM performance_evaluations e
    JOIN training_programmes p
      ON p.programme_id = e.programme_id
    JOIN specialization_areas sa
      ON sa.specialization_area_id = p.required_specialization_area_id
    GROUP BY e.trainer_id, sa.discipline_group
),
eval_groups AS (
    SELECT
        trainer_id,
        jsonb_object_agg(discipline_group, group_count) AS evaluations_by_group,
        jsonb_object_agg(discipline_group, group_mean)  AS mean_by_group
    FROM eval_per_group
    GROUP BY trainer_id
),
allocation_totals AS (
    SELECT
        a.trainer_id,
        count(*) FILTER (
            WHERE a.status IN ('PENDING_TRAINER', 'CONFIRMED', 'CONDUCTED')
        )                                 AS active_allocation_count,
        count(*)                          AS total_allocation_count,
        max(a.approval_date)              AS last_assignment_date
    FROM allocations a
    GROUP BY a.trainer_id
),
qualification_totals AS (
    SELECT tq.trainer_id, count(*) AS qualification_count
    FROM trainer_qualifications tq
    GROUP BY tq.trainer_id
),
specialization_totals AS (
    SELECT ts.trainer_id, count(*) AS specialization_count
    FROM trainer_specializations ts
    GROUP BY ts.trainer_id
)
SELECT
    t.trainer_id,
    COALESCE(ev.evaluation_count, 0)          AS evaluation_count,
    ev.mean_score_awarded,
    ev.last_evaluation_date,
    COALESCE(eg.evaluations_by_group, '{}'::jsonb)
                                              AS evaluations_by_discipline_group,
    COALESCE(eg.mean_by_group, '{}'::jsonb)   AS mean_by_discipline_group,
    COALESCE(al.active_allocation_count, 0)   AS active_allocation_count,
    al.last_assignment_date,
    COALESCE(al.total_allocation_count, 0)    AS total_allocation_count,
    COALESCE(q.qualification_count, 0)        AS qualification_count,
    COALESCE(s.specialization_count, 0)       AS specialization_count,
    t.profile_completeness
FROM trainers t
LEFT JOIN eval_totals           ev ON ev.trainer_id = t.trainer_id
LEFT JOIN eval_groups           eg ON eg.trainer_id = t.trainer_id
LEFT JOIN allocation_totals     al ON al.trainer_id = t.trainer_id
LEFT JOIN qualification_totals  q  ON q.trainer_id  = t.trainer_id
LEFT JOIN specialization_totals s  ON s.trainer_id  = t.trainer_id
"""

#: The original, incorrect definition. Restored verbatim on downgrade — a migration
#: that "downgrades" to something other than what was there is not reversible, it is
#: a second forward migration wearing a disguise.
ORIGINAL_VIEW = """
CREATE OR REPLACE VIEW v_trainer_scoring_facts AS
SELECT
    t.trainer_id,
    COALESCE(ev.evaluation_count, 0)               AS evaluation_count,
    ev.mean_score_awarded,
    ev.last_evaluation_date,
    COALESCE(ev.evaluations_by_group, '{}'::jsonb) AS evaluations_by_discipline_group,
    COALESCE(ev.mean_by_group, '{}'::jsonb)        AS mean_by_discipline_group,
    COALESCE(al.active_allocation_count, 0)        AS active_allocation_count,
    al.last_assignment_date,
    COALESCE(al.total_allocation_count, 0)         AS total_allocation_count,
    COALESCE(q.qualification_count, 0)             AS qualification_count,
    COALESCE(s.specialization_count, 0)            AS specialization_count,
    t.profile_completeness
FROM trainers t
LEFT JOIN LATERAL (
    SELECT
        count(*)                       AS evaluation_count,
        round(avg(e.score_awarded), 2) AS mean_score_awarded,
        max(e.evaluation_date)         AS last_evaluation_date,
        jsonb_object_agg(g.discipline_group, g.group_count)
            FILTER (WHERE g.discipline_group IS NOT NULL) AS evaluations_by_group,
        jsonb_object_agg(g.discipline_group, g.group_mean)
            FILTER (WHERE g.discipline_group IS NOT NULL) AS mean_by_group
    FROM performance_evaluations e
    LEFT JOIN LATERAL (
        SELECT
            sa.discipline_group,
            count(*) OVER (PARTITION BY sa.discipline_group) AS group_count,
            round(avg(e2.score_awarded) OVER (PARTITION BY sa.discipline_group), 2)
                AS group_mean
        FROM performance_evaluations e2
        JOIN training_programmes p2 ON p2.programme_id = e2.programme_id
        LEFT JOIN specialization_areas sa
          ON sa.specialization_area_id = p2.required_specialization_area_id
        WHERE e2.trainer_id = e.trainer_id AND e2.evaluation_id = e.evaluation_id
    ) g ON true
    WHERE e.trainer_id = t.trainer_id
) ev ON true
LEFT JOIN LATERAL (
    SELECT
        count(*) FILTER (
            WHERE a.status IN ('PENDING_TRAINER', 'CONFIRMED', 'CONDUCTED')
        ) AS active_allocation_count,
        count(*)             AS total_allocation_count,
        max(a.approval_date) AS last_assignment_date
    FROM allocations a
    WHERE a.trainer_id = t.trainer_id
) al ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS qualification_count
    FROM trainer_qualifications tq
    WHERE tq.trainer_id = t.trainer_id
) q ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS specialization_count
    FROM trainer_specializations ts
    WHERE ts.trainer_id = t.trainer_id
) s ON true
"""

COMMENT = (
    "Per-trainer aggregates for dashboards and reports. The prediction engine does "
    "not read this view — it computes its own facts in one query (see "
    "TrainerRepository.FACTS_SQL)."
)


def upgrade() -> None:
    """Replace the view with a set-based definition that groups correctly."""
    # DROP then CREATE rather than CREATE OR REPLACE: the two definitions produce the
    # same column list today, but CREATE OR REPLACE refuses any change to column names,
    # order, or types, and failing on a rename at deploy time is not a good surprise.
    op.execute("DROP VIEW IF EXISTS v_trainer_scoring_facts")
    op.execute(CORRECTED_VIEW)
    op.execute(f"COMMENT ON VIEW v_trainer_scoring_facts IS '{COMMENT}'")


def downgrade() -> None:
    """Restore the original definition, bug and all."""
    op.execute("DROP VIEW IF EXISTS v_trainer_scoring_facts")
    op.execute(ORIGINAL_VIEW)
    op.execute(f"COMMENT ON VIEW v_trainer_scoring_facts IS '{COMMENT}'")
