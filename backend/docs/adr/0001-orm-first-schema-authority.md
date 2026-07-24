# ADR-0001 — The ORM is the authority for the schema

**Status:** Accepted · 2026-07-23

## Context

The schema can be defined in one of two places: hand-written SQL DDL applied by
migrations, or SQLAlchemy declarative models from which migrations are generated.
Both are defensible, and choosing neither — which is the common failure — produces a
codebase where the models and the DDL drift apart until nobody trusts either.

TPS has a further constraint: Phase 2 builds an API on this schema using the same
SQLAlchemy models. If the models were a hand-maintained mirror of canonical DDL, every
schema change would need to be made twice, correctly, by hand.

## Decision

SQLAlchemy 2.0 declarative models in `app/models/` are the **single source of truth**.
Alembic migrations are produced by `--autogenerate` and then **hand-reviewed and
edited**. There is no hand-written canonical DDL.

Autogenerate is treated as a first draft, never as output. Migration 0001's docstring
records what the review confirmed it captured, and migration 0002 exists precisely
because autogenerate is blind to triggers, functions, sequences, and `EXCLUDE`
constraints.

## Alternatives considered

**Hand-written SQL DDL as canonical, models mirroring it.** Gives complete control
over the generated SQL and reads naturally to a DBA. Rejected because it doubles the
work of every change and guarantees eventual divergence: nothing mechanically checks
that the model matches the table, so the first mismatch is discovered as a runtime
error in production.

**Models canonical, migrations fully trusted from autogenerate.** Simplest workflow.
Rejected because autogenerate silently omits triggers, views, server defaults, index
methods, `CHECK` constraints in some configurations, and `EXCLUDE` constraints
entirely. Trusting it would have produced a schema with no audit immutability and no
`updated_at` maintenance, both of which look fine until they are needed.

**A schema-migration tool outside Python** (Flyway, Sqitch). Rejected: it reintroduces
the two-sources problem and adds a runtime dependency for no gain here.

## Consequences

- Schema changes start in `app/models/` and flow outward. Adding a model file without
  importing it in `app/models/__init__.py` is a **data-loss bug**, because Alembic
  will not see the table and will generate a migration dropping it. That is documented
  in the package docstring.
- `alembic revision --autogenerate` immediately after `upgrade head` must produce an
  empty migration. This is verified and is the standing drift check.
- The naming convention on `Base.metadata` is mandatory, not cosmetic: without
  deterministic constraint names, autogenerate produces phantom diffs forever.
- Anything Alembic cannot see must be hand-written and explicitly listed, which is
  what migration 0002 is for.
