# ADR-0004 — `VARCHAR` + `CHECK` and lookup tables, not native `ENUM`

**Status:** Accepted · 2026-07-23

## Context

The schema carries roughly twenty closed value sets: programme statuses, allocation
statuses, exclusion reasons, audit actions, account states, and so on. PostgreSQL
offers a native `ENUM` type, which is compact and self-documenting.

Some of these sets are *ordered* and carry *weight in the scoring algorithm* —
qualification levels and proficiency levels each have a rank and a score value.

## Decision

Three mechanisms, chosen by what the value has to do:

1. **`VARCHAR` + `CHECK ... IN (...)`** for status-like sets, mirrored by a Python
   `StrEnum` in `app/models/enums.py`. The `CHECK` clause is *generated from the enum*
   by `check_in()`, so the two cannot drift silently.
2. **Lookup tables with a foreign key** for values that need an ordering or a score:
   `qualification_levels`, `proficiency_levels`, `specialization_areas`,
   `training_categories`, `police_ranks`.
3. **Rows, not columns** for scoring weights — see ADR-0008 and D8.

## Alternatives considered

**Native PostgreSQL `ENUM`.** Compact, and the type system enforces membership.
Rejected because altering one is not cleanly reversible: `ALTER TYPE ... ADD VALUE`
cannot be rolled back within a transaction in the general case, and a value can never
be *removed* at all. Every one of these sets is expected to change as the system
matures — `AuditAction` already differs between this schema and the frontend's union.
A migration that cannot be downgraded is a migration that cannot be safely deployed.

**Free-text with application-level validation.** Rejected outright for
`specialization_areas`: BR-04 excludes a trainer who lacks the required
specialisation, and as free text that rule degrades into string comparison and fails
silently on "Cybercrime Investigations" versus "Cybercrime Investigation". A foreign
key makes the business rule structurally enforceable rather than conventionally
observed.

**Lookup tables for everything, including statuses.** Consistent, and avoids the
duplicated value lists. Rejected because a status has no attributes beyond its name —
a `programme_statuses` table would be a join on every query returning nothing the
string did not already say.

## Consequences

- Each value set exists in two places: the `StrEnum` and the `CHECK`. `check_in()`
  derives the second from the first, so adding a member produces a migration diff
  rather than a silent mismatch. This is the cost of the decision and it is paid
  deliberately.
- Score values are `UPDATE`-able rows, satisfying NFR-10's requirement that the
  scoring model be retunable without redeploying unrelated components.
- Ordered comparisons use `rank_order`, never the code. `'ACP' < 'PC'` is true
  alphabetically and false in every sense that matters.
- The `institution_type = 'POLICE'` column replaces the frontend's hard-coded set of
  institution *names*, so a newly added police school earns the qualification bonus
  automatically rather than after someone remembers to edit a constant.
