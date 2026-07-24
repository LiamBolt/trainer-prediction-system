# ADR-0010 — Store every prediction and exclusion, with no top-N truncation

**Status:** Accepted · 2026-07-23 (decision confirmed by the project owner)
**Arises from:** conflict C3 in `PROGRESS.md`

## Context

§7.1 states the seed should contain "~230 predictions across runs · 64 allocations ·
47 performance evaluations". Running the frontend's own mock generator and counting
gives different figures:

| Entity | §7.1 states | Measured in the mocks |
|---|---|---|
| Trainers | 812 | 812 ✅ |
| Programmes | 46 | 46 ✅ |
| Audit entries | ~600 | 600 ✅ |
| Notifications | 18 | 18 ✅ |
| **Predictions** | **~230** | **3,828 across 40 runs** |
| **Allocations** | **64** | **37** |
| **Evaluations** | **47** | **42** |

The "~230" figure is consistent with storing a top-N list per run. The engine actually
ranks every eligible trainer: the featured run alone produces 698 ranked candidates
and 114 exclusions from a pool of 812.

## Decision

Store **every** ranked candidate and **every** exclusion for every run. No truncation.

The seed as built produces 7,327 predictions and 25,153 exclusions across 40 runs —
higher than the mocks because this seed's trainers hold slightly different
specialisation distributions and because it simulates history chronologically.

## Alternatives considered

**Truncate to the top 25 per run**, roughly matching §7.1's stated figure. Smaller
tables, and the UI only displays a handful. Rejected because it destroys the Exclusion
Ledger, which §5.6 identifies as "the most under-appreciated table in the schema and
the one that most directly addresses the SRS problem statement". The system's central
claim is that it can answer "why isn't so-and-so on the list?" — and a truncated ledger
answers "I don't know" for everyone below the cut.

**Engineer the seed to hit §7.1's numbers exactly.** Matches the document literally.
Rejected: it would require suppressing real engine output to satisfy a figure that
demonstrably does not describe the mocks the same section calls authoritative.

**Store exclusions but truncate predictions.** Rejected as arbitrary — a candidate
ranked 300th is exactly as much a part of the record as one excluded by a gate.

## Consequences

- `predictions` and `prediction_exclusions` are the largest tables by an order of
  magnitude. At ~32,000 rows combined this is trivial for PostgreSQL; the seed writes
  all 37,831 rows in 17 seconds.
- Phase 2 **must paginate** these endpoints. Returning 698 ranked candidates in one
  response is the obvious next mistake, and the knowledge base's "paginate everything"
  rule applies with force here.
- `prediction_runs.ranked_count` and `excluded_count` are stored so summary displays
  never need to count rows.
- The composite index `ix_predictions_run_rank` on `(run_id, rank_position)` matches
  the access pattern exactly: filter by run, order by rank, page through.
- §7.1's stated volumes are recorded here as **incorrect for three of seven entities**
  rather than silently worked around, so a later reader does not rediscover the
  discrepancy as a bug.
