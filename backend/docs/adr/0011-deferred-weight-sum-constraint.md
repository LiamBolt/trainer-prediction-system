# ADR-0011 — Weight-sum enforcement, and exactly what it guarantees

**Status:** Accepted · 2026-07-23

## Context

A scoring policy's five criterion weights must sum to 100. §5.5 notes this "cannot be
expressed as a row-level `CHECK`" and asks for a deferred constraint trigger if one
can be added cleanly — and, pointedly, for the ADR to **state which guarantee was
actually achieved and not claim an invariant that was not implemented**.

A row-level `CHECK` sees only its own row, so it cannot observe a sum across five.

## Decision

A `CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY DEFERRED` on `scoring_policy_weights`,
firing `AFTER INSERT OR UPDATE OR DELETE`, calling `check_policy_weights_sum()`.

Because it is deferred, it runs at `COMMIT` — by which point all five rows of a new
policy exist. A transaction inserting a whole policy is therefore valid throughout and
checked once, at the end.

## What this guarantees — precisely

**Guaranteed:** no transaction can commit leaving a policy whose weights sum to
anything other than 0 or exactly 100. Verified by `scripts/verify.py`, which attempts
to set one weight to 5 and asserts the commit is rejected.

**Deliberately permitted:** a sum of exactly **0**, meaning a policy with no weight
rows. This is not an oversight. It is the state of a policy row that has just been
inserted before its weights, and the state left behind when a policy is deleted and
`CASCADE` removes its weights. Forbidding it would make it impossible to create a
policy at all.

**Not guaranteed:** that a policy *has* weights. A policy row with zero weight rows is
valid to the database. Nothing prevents `INSERT INTO scoring_policies` alone, and the
active policy could in principle be weightless.

**Not guaranteed:** that the five criteria present are the five expected ones. The
`CHECK` on `criterion_key` restricts each row to a valid member, and
`UNIQUE(policy_id, criterion_key)` prevents duplicates, but nothing requires all five
to be present. A policy with `SPECIALIZATION 100` and no other rows satisfies every
database constraint.

## Alternatives considered

**Application-layer validation only.** Rejected as insufficient on its own for a value
that determines allocation outcomes, though Phase 2 should validate too — a clear
error message beats a constraint violation.

**A non-deferred `AFTER` trigger.** Rejected: it fires after the first row, when the
sum is 30, and no valid policy could ever be inserted.

**Storing weights as five columns with a table-level `CHECK`.** Would make the sum a
plain `CHECK`. Rejected because it contradicts D8 — adding a sixth criterion would
become a schema migration, defeating NFR-10.

**A materialised `total_weight` column on `scoring_policies`, maintained by trigger,
with a `CHECK (total_weight = 100)`.** Genuinely closes the "policy with no weights"
gap. Rejected as disproportionate: it denormalises a derived value and still needs a
trigger to maintain it, and Phase 2's service layer is the natural place to require
that a policy be complete before activation.

## Consequences

- The two gaps above are **real and stated**. Phase 2's service layer must enforce
  that an activated policy carries exactly the five `CriterionKey` values, because the
  database does not.
- Error messages surface at `COMMIT` rather than at the offending statement, which can
  read as confusing. The exception text names the policy and the actual total to
  compensate.
- `scripts/verify.py` checks both the guarantee (bad sums rejected) and the seeded
  state (every policy sums to 100, exactly one active).
