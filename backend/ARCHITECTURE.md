# Architecture

*Trainer Prediction System — backend*

---

## The layering, and the one rule that matters

```
   app/api/          routers, dependencies          ← knows HTTP
        │
        ▼
   app/services/     business logic                 ← knows the domain
        │
        ▼
   app/repositories/ queries and projections        ← knows SQL
        │
        ▼
   app/models/       ORM entities                   ← knows the schema
```

**Dependencies point downward only.** The rule that keeps that true is stated in one
sentence and is checkable mechanically:

> **No module in `app/services/` imports `fastapi`.**

```bash
grep -rl "^from fastapi\|^import fastapi" app/services/    # must return nothing
```

A service that raises `HTTPException` can only be called from a web request. A service
that raises `ConflictError` can be called from a request, a background task, a CLI
script, or a test — and exactly one place, `app/core/problem_details.py`, decides that
`ConflictError` means 409.

Three consequences follow, and they are the reason for the rule rather than an
afterthought:

1. **Errors are translated once.** Every service exception maps to a status in one file.
   There is no route that returns a 400 where its neighbour returns a 409 for the same
   condition.
2. **Services are testable without a client.** The prediction engine has 77 unit tests
   and no HTTP anywhere in them.
3. **DTOs cross the boundary, never ORM entities (B3).** A router returns a Pydantic
   model. An `Allocation` object never reaches a response, so a lazy relationship can
   never be serialised by accident — which in async SQLAlchemy is not a slow query but a
   `MissingGreenlet` exception at render time.

---

## Request lifecycle

```
  request
     │
     ▼  CORS               allowlisted origins, credentials on
     ▼  CorrelationId      X-Request-ID in, or minted; on every log line and error body
     ▼  RequestLogging     structured line with method, path, status, duration
     ▼  AuditContext       IP and user agent into a contextvar
     ▼  GZip               responses over 1 KB
     │
     ▼  route dependencies
     │     get_db_session      ── opens the session, the transaction begins
     │     get_current_user    ── decodes the token, RE-READS account status,
     │                            fills in the audit actor
     │     require_roles(...)  ── layer 1 of authorisation
     │
     ▼  handler
     │     service call        ── layer 2: object-level ownership checks live in here
     │     audit.record(...)   ── same session, same transaction
     │
     ▼  dependency teardown
     │     session.commit()    ── ONE commit, at the edge
     │     or session.rollback() on any exception
     │
     ▼  BackgroundTasks        ── notification dispatch, after the response is sent
     │
  response
```

Middleware order is deliberate. Starlette applies middleware in reverse registration
order, so the last added is outermost; `create_app()` registers them bottom-up to
produce the order above. Correlation is outside logging so every log line has an id;
audit context is inside both so it sees the resolved request.

---

## Transaction boundaries

**One session per request. One transaction. One commit, at the edge.**

The approval path is the case that justifies the design. In one transaction it:

1. locks the programme row (`SELECT ... FOR UPDATE`)
2. re-checks the hard gates against live data
3. inserts the allocation with its five frozen columns
4. draws a registry number from a sequence
5. advances the programme to `AWAITING_RESPONSE`
6. writes the trainer's notification
7. records `ALLOCATION_APPROVED`

Any failure rolls back all seven. A partial success here is a notified trainer with no
allocation, or an allocation nobody was told about, and either is discovered weeks later
by a person rather than by a monitor.

**Audit writes participate in the transaction they describe (B8).** Not "afterwards", not
"best effort". If the mutation rolls back, the entry rolls back with it; if the entry
cannot be written, the whole operation fails. The asymmetry is the point: an audit log
that is *incomplete* is worse than none, because it is trusted — an investigator reading
a trail with no entry for an action concludes the action did not happen.

### The one deliberate exception

`AuthService._persist_then_raise` commits before raising. Failed sign-ins must persist
their attempt counter *and then* signal failure; without the explicit commit the session
dependency rolls back and FR-01's lockout never increments, so the account is never
locked however many attempts are made. It is annotated as the exception it is, and it
exists because the alternative is a security control that silently does nothing.

---

## Authorisation, in two layers

Both are required. Either alone is insufficient, and the second is the one usually
missing.

```python
# Layer 1 — role, on the route
@router.post("", dependencies=[Depends(require_roles(TA))])
async def approve(...): ...

# Layer 2 — object ownership, inside the service
if allocation.trainer_id != caller_trainer_id:
    raise ForbiddenError("You may only respond to your own assignments.")
```

Layer 1 answers *"may this kind of user do this kind of thing?"* Layer 2 answers *"may
**this** user do it to **this** record?"* — which a role check cannot express and which
is the entire content of OWASP's Broken Object Level Authorization.

Every authorisation failure writes `UNAUTHORISED_ATTEMPT` (NFR-04). A system that logs
only what it permitted cannot show what it refused.

`tests/integration/test_authorization.py` walks every route against every wrong role and
asserts 403 — and cross-checks its own matrix against the live OpenAPI schema, so a route
added next month without a line in the matrix fails the test rather than going quietly
untested. That last part is what stops a hand-maintained security checklist from rotting.

---

## Where the important things live

| Concern | Location | Note |
|---|---|---|
| Scoring engine | `app/services/prediction/` | Pure functions. No I/O, no ORM, no `fastapi`. |
| The facts query | `app/repositories/trainer_repo.py` | Eight CTEs, one round trip, 62–83 ms. |
| Freezing a decision | `app/services/allocation_service.py::_create_allocation` | The **only** place the five frozen columns are written. |
| Error → status mapping | `app/core/problem_details.py` | The only module that knows both. |
| Weights | `scoring_policy_weights` rows | Not code (D8, NFR-10). |
| Score/rating serialisation | `app/schemas/base.py` | Quantise, *then* convert. |

---

## How to add a new endpoint

1. **Schema** in `app/schemas/` — inherit `CamelModel`, so camelCase on the wire and
   snake_case in Python happens in one place and nowhere else.
2. **Service method** in `app/services/` — no `fastapi` import. Raise `NotFoundError`,
   `ConflictError`, `ForbiddenError`, or `BusinessRuleViolation`; never an
   `HTTPException`.
3. **Route** in `app/api/v1/` — `dependencies=[Depends(require_roles(...))]`, a
   `summary`, a `description` explaining *why* the rule exists, and a `responses` map
   naming each status.
4. **Register** it in `app/api/router.py`. A router not registered there does not exist,
   which is a failure that shows up immediately.
5. **Add it to the authorisation matrix** in `tests/integration/test_authorization.py`.
   The coverage test will fail until you do — deliberately.

---

## How to add a scoring criterion — with no migration

The criteria that *exist* are an enum; their *weights* are rows. Adding a sixth
criterion therefore needs no schema change:

1. Add a member to `CriterionKey` in `app/models/enums.py`.
2. Write a class in `app/services/prediction/criteria.py` implementing the `Criterion`
   protocol — `key`, `label`, and `score(facts, programme, prior_mean)` returning
   `(normalised, raw_value, explanation, data_quality)`.
3. Register it in the `CRITERIA` tuple.
4. Add whatever fact it needs to `CandidateFacts` and to `FACTS_SQL`.
5. `INSERT` a weight row and adjust the others so the five (now six) still total 100.
   The deferred constraint trigger checks the sum at commit, so a single transaction
   rebalancing all of them is valid throughout.

No migration, no deployment to retune, no column added. That is what D8 and NFR-10 buy.

---

## What is deliberately *not* here

**No repository abstraction over the ORM.** SQLAlchemy is already that. A second layer
of `IUserRepository` interfaces over it would add indirection without adding a seam
anybody is going to use — this system will not be ported off PostgreSQL, and the schema
depends on PostgreSQL-specific features (`JSONB`, `EXCLUDE USING gist`, partial indexes,
`citext`) that no abstraction would survive anyway.

**No message queue.** Notification dispatch is a `BackgroundTask`. At this scale, a
queue would be infrastructure to run, monitor and back up in exchange for a guarantee the
system does not currently need — and the notification *row* is already written
transactionally, so nothing is lost when dispatch fails.

**No caching layer.** Reference data carries `Cache-Control: max-age=300` and the browser
stops asking. Everything else is either a decision (must be current) or a report
(computed on demand and rarely).

**No soft deletes.** Programmes are `CANCELLED`, not deleted, once they have allocation
history. Audit entries cannot be deleted at all — a database trigger refuses it. A
`deleted_at` column would create rows that are simultaneously present and absent
depending on which query someone remembered to filter.
