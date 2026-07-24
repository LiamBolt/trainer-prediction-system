# ADR-0015 — Async SQLAlchemy, one session per request, committed at the edge

**Status:** Accepted · 2026-07-23

## Context

This API is I/O-bound almost entirely. The measured prediction run spends 62–83 ms in
one database query and single-digit milliseconds computing; nothing in it is CPU-bound.

## Decision

**SQLAlchemy 2.0 async with asyncpg.** One `AsyncSession` per request, yielded by the
`get_db_session` dependency, committed once when the handler returns and rolled back on
any exception.

Services receive that session. **They never create one.**

## Rationale

**Why async.** Under a synchronous stack, a worker blocks for the whole 83 ms of the
facts query. Async lets one worker serve other requests during that wait. For a workload
that is essentially "wait for PostgreSQL", this is the difference between concurrency
limited by worker count and concurrency limited by the database.

**Why one session per request.** It is what makes a multi-step operation atomic. The
approval path creates the allocation, freezes five columns, advances the programme,
writes the notification, and records the audit entry. All of it is one transaction
because all of it uses one session. A service that opened its own would produce partial
success — a notified trainer with no allocation, or an allocation nobody was told about —
and either is discovered weeks later by a person, not by a monitor.

**Why commit at the edge, not in the service.** A service that commits cannot be composed:
the moment two of them are called in one request, the first has already committed when
the second fails. Keeping the boundary in the dependency means composition is free and
the rule is enforced structurally rather than by discipline.

## Consequences

**Good.** Atomicity is the default rather than something each service must remember.
Audit writes participate in the mutation's transaction (B8) — if the mutation rolls back,
so does its audit entry, and an audit log that is trusted but lossy is more dangerous
than none.

**Costs.**

`lazy="raise_on_sql"` on every relationship. In async SQLAlchemy a lazy load is not slow,
it is a `MissingGreenlet` exception — so relationships must be loaded explicitly. The
setting turns a runtime surprise into an immediate, obvious error at development time.

`expire_on_commit=False`, because the default expires every attribute on commit and the
next access triggers a refresh, which in async is again `MissingGreenlet`.

**One deliberate exception to the rule.** Failed sign-ins must persist their attempt
counter *and then* raise, or the session dependency rolls back and FR-01's lockout never
increments — the account is never locked, however many attempts are made. `AuthService`
commits explicitly before raising, in `_persist_then_raise`. This is the only place in
the codebase where a service commits, it is annotated as such, and it exists because the
alternative is a security control that silently does nothing.

**Testing.** `app.db.session.engine` is module-level and its pooled connections bind to
the event loop that first used them. pytest-asyncio gives each test a fresh loop, so an
autouse fixture disposes the engine between tests; without it, the second test onwards
fails with `got Future attached to a different loop` from deep inside asyncpg, nowhere
near the actual test.
