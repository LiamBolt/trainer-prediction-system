# ADR-0006 — A prediction is not an allocation, and the score is frozen

**Status:** Accepted · 2026-07-23

## Context

The prediction engine ranks trainers. An administrator approves one. The Decision
Receipt shown afterwards must display the score, rank, breakdown, weights, and
rationale **as they stood at the moment of approval**.

Two design questions follow. Are a ranking and a decision the same record? And should
the receipt re-derive the score on read, or store it?

## Decision

**Separate tables**, joined by a `UNIQUE` constraint on `allocations.prediction_id`,
giving a one-to-zero-or-one relationship (D7).

**Five frozen columns** on `allocations`: `frozen_score`, `frozen_rank_position`,
`frozen_breakdown`, `frozen_weights`, `frozen_rationale`. Written once at approval and
never recalculated.

`frozen_rationale` and `weights_were_simulated` are required by
`frontend/src/types/domain.ts` but were absent from the specification's column list;
both are included (conflict C5).

## Alternatives considered

**One table with a nullable `approved_at`.** Fewer joins, and the relationship is
implicit. Rejected: deleting a superseded ranking would then be the same operation as
deleting a government decision, and the two have opposite retention requirements. Most
predictions never become allocations and must survive as history; every allocation
must survive permanently.

**Re-deriving the score on read.** No duplication, and the receipt always reflects the
current model. Rejected because it is *actively wrong*: an evaluation recorded next
month changes the PERFORMANCE criterion, so the receipt for a decision taken today
would silently rewrite itself. Freezing is the difference between an audit record and
a rendering — a rendering shows what the system thinks now, and the question being
asked is what the officer saw then.

**Storing only `frozen_score` and re-deriving the breakdown.** Rejected for the same
reason at finer grain: the breakdown *is* the justification, and a total without its
components explains nothing.

**Event sourcing the whole decision history.** Rejected as disproportionate. The
frozen snapshot answers the one question that is actually asked ("what did you see?")
without a projection layer.

## Consequences

- The frozen JSONB duplicates data also present in `predictions`. This is intentional
  duplication with a stated purpose, not normalisation failure, and is documented as
  such in the model docstring.
- Re-running a prediction marks the previous run `is_superseded` rather than deleting
  it, so the ranking an allocation was based on remains reachable.
- `superseded_by_allocation_id` links the chain when a decline promotes the next
  candidate, so the full sequence of decisions is traversable.
- The `UNIQUE` constraint on `prediction_id` is what enforces the cardinality.
  `verify.py` asserts no prediction carries two allocations.
