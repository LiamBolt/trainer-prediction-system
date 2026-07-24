# ADR-0012 — Build §6 as canonical; alias cosmetic mismatches; refuse insecure ones

**Status:** Accepted · 2026-07-23

## Context

`frontend/` was built first, against a mock adapter, and its `src/api/endpoints/` are a
working client. §6 of the backend specification defines a different surface. Reconciling
the two produced **14 mismatches** (recorded in `PROGRESS.md` §P2.2), which fall into
four groups.

The instruction in §0 is that a mismatch must be *raised*, not silently resolved. This
ADR is that record.

## Decision

**Build §6 as canonical.** Register the frontend's paths as **aliases** on the same
handlers where the difference is cosmetic. **Refuse** the four where the frontend's
design is insecure.

### Group A — aliased (path or method only, same semantics)

| Frontend calls | §6 specifies |
|---|---|
| `POST /programmes/{id}/requirements` | `PUT` |
| `GET /programmes/{id}/eligibility` | `/eligibility-preview` |
| `POST /scoring-policy` | `PUT` |
| `GET /reports/allocations` | `/reports/allocation-history` |
| `GET /reports/performance` | `/reports/performance-trends` |
| `GET /trainers/{id}/evaluations` | `/evaluations/trainer/{id}` |
| `POST /allocations/{id}/accept` · `/decline` | `/trainers/me/assignments/{id}/…` |
| `GET /dashboard?role=` | `/dashboard/summary` |

Aliases are registered with `include_in_schema=False`, so the documented surface stays
single while the existing client keeps working unchanged. **No alias weakens a check**:
each one reaches the same handler, with the same dependencies, and identity still comes
from the token.

### Group B — refused 🔴

| # | Frontend calls | Problem |
|---|---|---|
| B1 | `GET /me/trainer?userId=<id>` | Identity from a **query parameter**. Any authenticated user reads any trainer's profile by changing the number. Textbook IDOR. |
| B2 | `PATCH /trainers/{id}` for self-update | Same class: the caller supplies their own id. |
| B3 | `GET /dashboard?role=<role>&userId=<id>` | **The caller declares their own role.** A Trainer can request the Administrator dashboard. |
| B4 | `GET /notifications?recipientId=<id>` | Read another user's notifications by changing the id. |

These four are **not** aliased. Building them as the frontend currently calls them would
ship four authorisation bypasses into a government system.

Where the parameter exists in the frontend's current request, it is **accepted by HTTP
and discarded** — marked `deprecated` in the OpenAPI schema — so the existing client
does not receive a 422 while Phase 3 corrects the four call sites. Accepting and
ignoring is not the same as honouring: `GET /dashboard/summary?role=SYSTEM_ADMINISTRATOR`
as a Trainer returns the *Trainer* dashboard, and there is a test that says so.

## Consequences

**Good.** The API is secure by construction rather than by convention. The frontend keeps
working during Phase 3 rather than breaking on the first request. The documented surface
is §6's, so the OpenAPI export is a clean statement of intent.

**Costs.** Eight extra route registrations to maintain. Four frontend call sites must
change in Phase 3, and until they do, three screens (trainer self-service, dashboard,
notifications) work only because the server ignores what they send — which is correct
behaviour that *looks* like a client bug if you read only the client.

**Rejected alternative: implement the frontend's paths as specified.** This was the
faster option and would have needed no Phase 3 work. It was rejected because the four
Group B endpoints are not stylistic differences — they are the OWASP Broken Object Level
Authorization pattern, in a system holding police personnel records.
