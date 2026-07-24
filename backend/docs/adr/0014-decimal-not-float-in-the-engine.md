# ADR-0014 — `Decimal` end to end in the scoring engine

**Status:** Accepted · 2026-07-23

## Context

ADR-0003 settled the *storage* question: `NUMERIC`, not `double precision`. This ADR
covers the computation, which is a separate decision — a system can store `NUMERIC` and
still compute in floats, and many do.

## Decision

**No float appears anywhere in the scoring path.** Weights, normalised values,
contributions, totals, the shrinkage estimator, and the exponential decay in the
confidence function are all `Decimal`. The decay uses `Decimal.ln()` and `Decimal.exp()`
rather than `math.exp`.

Quantisation to two places with `ROUND_HALF_UP` happens **once**, at serialisation, and
the value is converted to a JSON number only after it is already exact.

## Rationale

IEEE-754 binary floating point cannot represent most decimal fractions exactly, and the
error accumulates through summation:

```python
>>> 45 * 88.7 / 100 + 20 * 91.2 / 100 + 15 * 76.4 / 100
75.15500000000002
```

Two candidates whose true scores are identical to two decimal places can compare unequal.
Which one wins depends on the order of summation, which depends on the order rows came
back from the database — which is not guaranteed between runs.

**An allocation decision that does not reproduce is not auditable.** That is the whole
argument. A ranking that reorders on recomputation cannot be defended eighteen months
later, and defensibility is this system's primary requirement.

`ROUND_HALF_UP` rather than Python's default banker's rounding, because half-up is what a
person checking the arithmetic by hand will do, and the Score Ledger exists to be checked
by hand.

## Consequences

**Good.** Byte-identical rankings across runs. The Score Ledger's contributions sum to
the total exactly, not approximately. Ties are broken by the documented tie-break rules
rather than by floating-point noise.

**Costs.** `Decimal` arithmetic is roughly an order of magnitude slower than float. At
n = 812 and c = 5 that is around 4,000 operations — immaterial against a run that spends
62–83 ms in the database and 347 ms overall. The cost would matter at a scale this system
will not reach.

The wire format is still a JSON **number**, not a string, because
`frontend/src/types/domain.ts` types every score as `number` and that contract is binding.
Exactness is preserved up to the boundary; what crosses it is already rounded.
