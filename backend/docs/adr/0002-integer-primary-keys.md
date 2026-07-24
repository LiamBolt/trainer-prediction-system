# ADR-0002 — Integer primary keys, not UUIDs

**Status:** Accepted · 2026-07-23

## Context

Every table needs a surrogate key. The modern default in many projects is a UUID,
usually justified by distributed generation and by not leaking row counts.

TPS has a hard external constraint: `frontend/src/types/domain.ts` types **every**
identifier as `number` — `trainerId: number`, `programmeId: number`,
`allocationId: number`. That file is a binding contract, already implemented against.

## Decision

`BIGINT GENERATED ALWAYS AS IDENTITY` for every primary key.

Human-facing identity is carried by **registry numbers** (`TPS/ALL/2026/0417`), not by
the primary key. Those are what appear on printed records and what an officer quotes
over the telephone.

`GENERATED ALWAYS` rather than `BY DEFAULT`, so an application cannot supply its own
value and collide with the sequence.

## Alternatives considered

**UUIDv4 primary keys.** Rejected on the contract: a UUID serialises as a string, and
TypeScript would accept `"a3f2…"` where it expects `number` only by failing at
runtime, far from the cause. Also costs 16 bytes against 8, randomises B-tree insert
locations, and bloats every one of the 40+ foreign keys in this schema.

**UUIDv7.** Solves the index-locality problem and is genuinely attractive for
distributed systems. Rejected for the same contract reason, and because TPS is a
single-database system with no shard-merge or offline-generation requirement — the
problem UUIDv7 solves does not exist here.

**Composite natural keys** (e.g. force number as the trainer key). Rejected: force
numbers are reassigned and corrected in practice, and a primary key that changes
propagates through every referencing row.

**`SERIAL`.** Rejected as the legacy spelling; `GENERATED ALWAYS AS IDENTITY` is
standard SQL, and `SERIAL` leaves the sequence's ownership and permissions implicit.

## Consequences

- Sequential ids leak approximate row counts and creation order. Accepted: this is an
  internal government system behind authentication, and the audit trail deliberately
  exposes ordering anyway.
- Registry numbers do the work of public identifiers, and are generated from
  PostgreSQL sequences (§5.9) rather than from the primary key.
- `BIGINT` rather than `INTEGER` because `prediction_exclusions` alone accrues ~25,000
  rows per full seed; a system running for years past four billion rows is implausible,
  but the eight bytes are already being spent on alignment.
