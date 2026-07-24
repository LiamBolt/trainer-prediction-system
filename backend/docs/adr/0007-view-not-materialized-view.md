# ADR-0007 — `v_trainer_scoring_facts` is a plain view

**Status:** Accepted · 2026-07-23

## Context

Every prediction run needs, per trainer: evaluation count, mean rating, most recent
evaluation date, per-discipline breakdowns, current workload, and last assignment
date. Computing these inline would repeat a five-way aggregation in every query that
scores candidates.

A view centralises it. The question is whether it should be materialized.

## Decision

A **plain `VIEW`**, built from `LEFT JOIN LATERAL` subqueries — one per fact group —
rather than a single `GROUP BY` across several joined tables.

## Alternatives considered

**Materialized view with periodic refresh.** Faster reads, at the cost of staleness.
Rejected because it breaks the SRS feedback loop: FR-10 exists so that recording an
evaluation influences future allocation decisions, and a materialized view would let
an evaluation recorded five minutes ago fail to affect the next prediction run. The
resulting bug — "I recorded the rating but the ranking didn't change" — is exactly the
behaviour the requirement forbids, and would be diagnosed as a scoring error rather
than a caching one.

**Materialized view with `REFRESH ... CONCURRENTLY` on write.** Removes the staleness
but adds a full recompute on every evaluation insert, which is strictly worse than
computing on read at this scale.

**No view; aggregate in the service layer.** Rejected: it means fetching evaluation
and allocation rows for hundreds of candidates to average them in Python, which is the
design smell the knowledge base names explicitly. Aggregation belongs in SQL.

**A single `GROUP BY` over joined tables.** Rejected as *incorrect*, not merely
slower: joining `performance_evaluations` and `allocations` to `trainers` in one query
fans the rows out, and both counts are silently multiplied by the other's cardinality.
The `LATERAL` form keeps each aggregate over its own relation.

## Consequences

- At 812 trainers the aggregation is milliseconds and always current.
- **Revisit past roughly 50,000 trainers.** At that point measure with
  `EXPLAIN (ANALYZE, BUFFERS)` before changing anything; if the view genuinely
  dominates a prediction run, a materialized view with `REFRESH CONCURRENTLY` triggered
  on evaluation insert is the next step, and the staleness window must then be
  documented in the UI.
- Per-discipline facts are returned as JSONB maps rather than by changing the view's
  grain to trainer × group. This keeps one row per trainer — which is what every
  consumer wants — while still answering "how many evaluations in this programme's
  group?" in a single lookup.
- The view is excluded from Alembic autogenerate by `include_object()` in
  `migrations/env.py`; Alembic reflects views as tables and would otherwise propose
  dropping it on every run.
