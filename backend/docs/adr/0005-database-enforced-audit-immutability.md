# ADR-0005 — Audit immutability enforced by the database

**Status:** Accepted · 2026-07-23

## Context

FR-13 states that audit entries cannot be edited or deleted **by any role**. An audit
trail that a sufficiently privileged user can alter provides the appearance of
accountability without the substance, which is worse than no trail at all — it invites
reliance on evidence that may have been edited.

The application layer is the obvious place to enforce this, and the wrong one: a
service-layer rule is one ORM call, one raw `text()` statement, or one `psql` session
away from being untrue.

## Decision

A `BEFORE UPDATE OR DELETE` trigger on `audit_logs` calls `prevent_audit_mutation()`,
which unconditionally raises with `ERRCODE = 'restrict_violation'`.

`audit_logs` also has **no `updated_at` column**. The column would be a lie: nothing
is ever updated, and a column that can only hold one value is misinformation in the
data dictionary.

`scripts/verify.py` attempts a real `UPDATE` and a real `DELETE` on every run and
fails if either succeeds. A constraint nobody has tried to violate is a constraint
nobody knows works.

## Alternatives considered

**Service-layer enforcement only.** Rejected as above — it protects against intent,
not against mistakes, and not at all against direct database access.

**Revoking `UPDATE`/`DELETE` from the application role.** Genuinely good, and
complementary rather than alternative. Not adopted *instead* because the application
role owns the table in this deployment, so it could grant the privilege back; and
because a `GRANT` is invisible in the migration history, whereas a trigger is a schema
object that appears in a diff. Worth adding in Phase 2 as defence in depth.

**Append-only via a write-only view with an `INSTEAD OF` trigger.** Rejected as
indirection: the same guarantee, one more object, and a table whose real name has to
be kept out of application code by convention.

**PostgreSQL row-level security.** Rejected: RLS governs which rows a role may see and
modify, not whether modification is permitted at all, and it does not apply to the
table owner by default.

## Consequences

- **`TRUNCATE` is not blocked.** The trigger is `FOR EACH ROW` on `UPDATE OR DELETE`;
  `TRUNCATE` fires only `TRUNCATE` triggers and requires table ownership. This is
  deliberate and is what allows `scripts/reset.py` to clear a development database.
  The threat model FR-13 addresses is *users of the application* tampering with the
  record; whoever holds table ownership on the production server is outside it and is
  controlled by database privileges instead. **This is stated plainly rather than
  claimed as absolute immutability, because it is not.**
- A genuine correction to an audit entry is impossible by design. The remedy is a new
  compensating entry, which is how paper registers work and is the correct model.
- Bulk deletion for retention policy would require dropping the trigger, performing
  the deletion, and recreating it — an explicit, reviewable migration rather than an
  ad-hoc `DELETE`. That friction is the feature.
