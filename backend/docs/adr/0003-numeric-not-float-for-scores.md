# ADR-0003 — `NUMERIC` for every auditable number

**Status:** Accepted · 2026-07-23

## Context

Prediction scores, confidence levels, criterion weights, and evaluation ratings are
all decimal quantities. `DOUBLE PRECISION` is the faster and more obvious choice for
anything called a "score".

These numbers are not telemetry. They are the recorded justification for a decision
about a person's career, taken by a named officer, and they must reproduce exactly
when re-read years later.

## Decision

`NUMERIC` for every auditable quantity:

| Value | Type |
|---|---|
| `prediction_score`, `confidence_level`, `frozen_score` | `NUMERIC(5,2)` |
| `scoring_policy_weights.weight` | `NUMERIC(5,2)` |
| `qualification_levels.score_value`, `proficiency_levels.score_value` | `NUMERIC(5,2)` |
| `performance_evaluations.score_awarded` | `NUMERIC(2,1)` |

In Python these map to `decimal.Decimal`. The seed's scoring port computes entirely in
`Decimal` with explicit `ROUND_HALF_UP` quantisation, never in `float`.

## Alternatives considered

**`DOUBLE PRECISION`.** Faster arithmetic and smaller storage. Rejected: binary
floating point cannot represent `0.1` exactly, so a weighted sum of five criteria has
no guarantee of reproducing bit-for-bit across platforms or library versions. A
Decision Receipt that renders `87.30000000000001` — or worse, renders `87.3` today and
`87.29` after a library upgrade — is not an audit record.

**Integers scaled by 100** (storing 8730 for 87.30). Exact and fast, and a legitimate
choice used in financial systems. Rejected because every read and write needs a
scaling step, and the first place someone forgets it is a defect that looks like a
factor-of-100 error in a government report. `NUMERIC` puts the scale in the schema
where it cannot be forgotten.

**`float` in Python with `NUMERIC` storage.** Rejected as the worst of both: exact
storage of an already-inexact computation. The rounding error happens before the
database sees it.

## Consequences

- Arithmetic is slower. Irrelevant at this scale: a prediction run scores a few
  hundred candidates, and the measured seed writes 37,831 rows in 17 seconds.
- Python code must use `Decimal` consistently. Mixing `Decimal` and `float` raises
  `TypeError`, which is the desired behaviour — it fails loudly at the boundary rather
  than silently degrading precision.
- JSONB payloads (`breakdown`, `frozen_weights`) store JSON numbers, which are
  double-precision by specification. This is accepted because those payloads are
  *display* copies of values whose authoritative form is the `NUMERIC` column beside
  them; the ledger's arithmetic is never re-derived from the JSON.
