# API guide

*Trainer Prediction System — `/api/v1`*

Interactive documentation: **`/docs`** (Swagger UI) · **`/redoc`** · machine-readable
schema at **`/openapi.json`**, also committed to `docs/openapi.json` so API changes
appear as reviewable diffs.

---

## Conventions

**camelCase on the wire, snake_case in Python.** Every request and response uses
camelCase — `predictionScore`, `forceNumber`, `rankPosition`. Requests also accept
snake_case, so a client sending the other spelling is not rejected for a cosmetic reason.

**Scores are JSON numbers, not strings.** Quantised to two decimal places before
conversion, so `87.4` never arrives as `87.40000000000001`. Ratings use one decimal.

**Times are ISO-8601 with an offset.** Every timestamp is `TIMESTAMPTZ` in the database;
none is ambiguous about its zone. Dates without a time (course dates, evaluation dates)
are plain `YYYY-MM-DD`, because a course does not start at a moment.

---

## Authentication

### Sign in

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin.training", "password": "Tps@2026#Demo"}
```

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "refreshToken": "QkX9Zt...",
  "expiresIn": 900,
  "user": {
    "userId": 1,
    "username": "admin.training",
    "fullName": "Grace Nabirye",
    "role": "TRAINING_ADMINISTRATOR",
    "rankCode": "SSP",
    "trainerId": null,
    "mustChangePassword": false
  }
}
```

Send the access token on every subsequent request:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Refresh — and why you must implement it

**The access token lasts 15 minutes.** Without a refresh flow the user is signed out
every quarter of an hour.

```http
POST /api/v1/auth/refresh
{"refreshToken": "QkX9Zt..."}
```

Returns a new access token **and a new refresh token**. The old refresh token is now
revoked — they are single-use.

> **Presenting an already-used refresh token revokes the entire family**, signing the
> session out everywhere. This is not a bug to work around: replay means either an
> attacker or the legitimate user is using a token the other has already spent, which is
> the signature of a stolen token. Store the newest refresh token and discard the old one
> immediately.

### Account lockout (FR-01)

Five consecutive failures lock the account for **15 minutes**:

```json
{
  "type": "https://tps.upf.go.ug/errors/account-locked",
  "title": "Account locked",
  "status": 423,
  "detail": "Too many failed sign-in attempts. This account is locked for 15 minutes.",
  "retryAfterSeconds": 900
}
```

Separately, sign-in is rate-limited to **10 attempts per minute per address** (429).

---

## Envelopes

### Lists

Every list endpoint returns the same shape. No variations.

```json
{
  "items": [ ... ],
  "page": 1,
  "pageSize": 20,
  "total": 812,
  "totalPages": 41
}
```

Parameters: `page` (1-based), `pageSize` (max 100), `sortBy`, `sortDir` (`asc`/`desc`).

`sortBy` is validated against a **per-endpoint allowlist**. An unknown value is a 422,
not a silent fallback — a silent fallback means the client thinks it sorted and did not.

**Exception: `/predictions/runs/{id}` has no `sortBy`.** BR-05 fixes the order absolutely.
Letting a client re-sort a ranked list would let the interface show a different
recommendation from the one recorded.

### Keyset pagination — the audit log

`/audit` supports both. Keyset is the documented path:

```http
GET /api/v1/audit?pageSize=50
GET /api/v1/audit?pageSize=50&after=eyJ0IjogIjIwMjYtMDktMTRU...
```

```json
{"items": [...], "pageSize": 50, "nextCursor": "eyJ0Ijo...", "hasMore": true}
```

Offset paging works too, and is **capped at 10,000 rows**. Past that the API returns 422
and tells you to use the cursor: the audit log only grows, and `OFFSET 200000` makes
PostgreSQL walk and discard 200,000 rows for every request.

### Errors — RFC 9457, one shape everywhere

```json
{
  "type": "https://tps.upf.go.ug/errors/business-rule-violation",
  "title": "Business rule violation",
  "status": 409,
  "detail": "This programme has no required specialisation yet. Define the requirements before generating a ranking — without them there is nothing to match trainers against.",
  "instance": "/api/v1/programmes/48/predict",
  "requestId": "69c78857005248988d27f22178f817c0",
  "businessRule": "FR-05"
}
```

Validation failures use the same envelope with an `errors` array:

```json
{
  "status": 422,
  "detail": "The information supplied could not be accepted. Weights must total 100, but they total 105.",
  "errors": [{"field": "weights", "message": "Weights must total 100, but they total 105."}]
}
```

`detail` is written for an officer and can be shown verbatim. `requestId` matches the
`X-Request-ID` response header and appears on every server log line for that request —
quote it when reporting a problem.

| Status | Meaning here |
|---|---|
| 400 | Malformed request |
| 401 | Not signed in, or the token is invalid or expired |
| 403 | Signed in, but not permitted — role **or** ownership |
| 404 | Not found, **or** found and not yours (deliberately indistinguishable) |
| 409 | A business rule or state conflict — the `detail` says which |
| 422 | Validation failed |
| 423 | Account locked (FR-01) |
| 429 | Rate limited |

---

## The RBAC matrix

TA = Training Administrator · TO = Training Officer · TR = Trainer · SA = System
Administrator

| Endpoint group | TA | TO | TR | SA |
|---|:-:|:-:|:-:|:-:|
| `GET /reference/*` | ✅ | ✅ | ✅ | ✅ |
| `GET /trainers` (directory) | ✅ | ✅ | — | ✅ |
| `GET /trainers/{id}` | ✅ | ✅ | own only | ✅ |
| `/trainers/me/*` | — | — | ✅ | — |
| `GET /programmes` | ✅ | ✅ | ✅ | ✅ |
| `POST /programmes`, `PUT .../requirements` | ✅ | ✅ | — | — |
| `POST .../predict`, `GET .../prediction` | ✅ | ✅ | — | — |
| `POST /predictions/simulate` | ✅ | — | — | — |
| `GET /scoring-policy` | ✅ | — | — | ✅ |
| `PUT /scoring-policy` | — | — | — | ✅ |
| `POST /allocations` **(the decision)** | ✅ | — | — | — |
| `GET /allocations/{id}` | ✅ | ✅ | assignee | ✅ |
| `/allocations/{id}/promote-next` · `/mark-conducted` · `/withdraw` | ✅ | — | — | — |
| `/trainers/me/assignments/{id}/accept` · `/decline` | — | — | ✅ | — |
| `POST /evaluations` | ✅ | — | — | — |
| `GET /evaluations/trainer/{id}` | ✅ | ✅ | own only | ✅ |
| `/notifications/*` | own | own | own | own |
| `GET /dashboard/summary` | ✅ | ✅ | ✅ | ✅ (role from the token) |
| `/reports/*` | ✅ | — | — | ✅ |
| `/users/*` | — | — | — | ✅ |
| `GET /roles` | ✅ | — | — | ✅ |
| `GET /audit` · `/export` | — | — | — | ✅ |
| `GET /audit/entity/{type}/{id}` | ✅ | — | — | ✅ |
| `/system/health/*` | — | — | — | ✅ |

**"own only" is enforced inside the service**, not by the role gate. A Trainer requesting
another trainer's record receives 403, not a filtered 200.

**`POST /allocations` is TA-only because BR-02 says so**, and BR-06 requires the approval
to be explicit. There is no auto-approve, no "accept top result", and no bulk approve
anywhere in this API.

---

## A worked scenario, end to end

### 1. Raise the request (FR-04) — as a Training Officer

```http
POST /api/v1/programmes
{"title": "Cybercrime Investigation Refresher", "categoryId": 1,
 "startDate": "2026-10-21", "endDate": "2026-11-02", "stationId": 1,
 "expectedParticipants": 25}
```

`201` · `Location: /api/v1/programmes/50` · status `DRAFT`, registry `TPS/REQ/2026/0050`.

Requirements are **not** accepted here. FR-05 defines them separately, which is what
makes `DRAFT → REQUIREMENTS_SET` a real event rather than a flag.

### 2. Check before you spend a run

```http
GET /api/v1/programmes/50/eligibility-preview?requiredSpecializationAreaId=1&minimumExperience=3
```

```json
{"eligible": 452, "total": 812, "message": "452 of 812 trainers meet these criteria"}
```

Gates only, no scoring — so an officer learns their criteria are too narrow *before*
generating a ranking.

### 3. Define the requirements (FR-05)

```http
PUT /api/v1/programmes/50/requirements
{"requiredSpecializationAreaId": 1, "minimumExperience": 3,
 "minimumQualificationLevelId": 4}
```

Status → `REQUIREMENTS_SET`. If a run already exists, this also sets
`requirementsChangedSincePrediction`, which is what raises the amber re-run banner — the
ranking on screen was computed against different criteria and is now stale.

### 4. Generate the ranking (FR-06)

```http
POST /api/v1/programmes/50/predict
```

```json
{
  "runId": 43, "rankedCount": 705, "excludedCount": 107,
  "candidatePoolSize": 812, "elapsedMs": 209,
  "weights": {"SPECIALIZATION": 30, "PERFORMANCE": 25, "EXPERIENCE": 20,
              "QUALIFICATION": 15, "AVAILABILITY": 10},
  "predictions": [
    {
      "predictionId": 30412, "rankPosition": 1,
      "trainerId": 4, "trainerName": "Ibrahim Wekesa", "trainerRank": "ASP",
      "predictionScore": 96.24, "confidenceLevel": 33, "confidenceBand": "LOW",
      "breakdown": [
        {"key": "SPECIALIZATION", "label": "Specialisation match", "weight": 30,
         "rawValue": "Expert · Cybercrime Investigation", "normalized": 100,
         "contribution": 30, "explanation": "Holds Expert proficiency in Cybercrime Investigation.",
         "dataQuality": "COMPLETE"}
      ],
      "rationale": "ASP Wekesa holds Expert proficiency in Cybercrime Investigation and has 20 years of service, but has no recorded evaluations yet.",
      "counterfactual": null
    }
  ]
}
```

**The contributions sum to `predictionScore` exactly.** Check it by hand — that is the
entire reason for choosing an additive model.

**`confidenceLevel` is data completeness, not likelihood of success.** `LOW` means the
system knows little about this trainer. It is not a prediction that they will do badly.

### 5. Why is so-and-so not on the list?

```http
GET /api/v1/predictions/runs/43/exclusions
```

```json
[{"reason": "BELOW_MINIMUM_QUALIFICATION", "businessRule": "FR-05", "count": 228,
  "trainers": [{"trainerId": 91, "fullName": "…", "policeRank": "IP",
                "reasonDetail": "Highest qualification is certificate; bachelor's degree required."}]}]
```

Every entry carries a rule citation and a sentence written for a non-technical reader.

### 6. Approve (FR-08) — as a Training Administrator

```http
POST /api/v1/allocations
{"predictionId": 30412, "remarks": "Strongest match on specialisation."}
```

`201` with the **Decision Receipt**: `frozenScore`, `frozenBreakdown`,
`frozenRankPosition`, `frozenWeights`, `frozenRationale`, the approving officer with
their rank, and `TPS/ALL/2026/0157`.

The server re-checks the hard gates against **live** data first. A trainer who became
unavailable since the run is refused:

```json
{"status": 409,
 "detail": "ASP Ibrahim Wekesa can no longer be assigned to this course: Marked unavailable for assignment. (BR-03). This changed after the ranking was generated. Approve another candidate, or re-run the prediction."}
```

`weights` and `weightsWereSimulated` in the body are accepted for compatibility and
**ignored** — the frozen weights come from the run itself.

### 7. The trainer answers (FR-09)

```http
GET  /api/v1/trainers/me/assignments
POST /api/v1/trainers/me/assignments/157/decline
{"reason": "Deployed to Karamoja for the operation covering these dates."}
```

The reason is required — 422 without it, and a database `CHECK` refuses any declined row
that lacks one.

### 8. Promote the next candidate (FR-08)

```http
POST /api/v1/allocations/157/promote-next
```

```json
{"reusedExistingRun": true, "runId": 43,
 "skipped": ["SP Agnes Nabirye (rank 2): Marked unavailable for assignment."],
 "message": "SSP Julius Wekesa has been offered the assignment, taken from the same ranking (run 43). No new prediction was generated."}
```

**`reusedExistingRun` is always `true`.** FR-08 requires that a decline does not trigger
a new prediction — the sequence of offers has to be explainable from one document.

### 9. Conduct and evaluate (FR-10)

```http
POST /api/v1/allocations/158/mark-conducted
POST /api/v1/evaluations
{"allocationId": 158, "scoreAwarded": 4.5,
 "evaluatorComments": "Clear delivery, strong command of the case-study material.",
 "evaluationDate": "2026-11-03"}
```

```json
{"evaluation": {"registryNumber": "TPS/EVL/2026/0047", "scoreAwarded": 4.5},
 "message": "Recorded. This score now informs future rankings for ASP Betty Nabirye."}
```

409 unless the allocation is `CONDUCTED`. One evaluation per allocation — a second
attempt is a 409, never a silent overwrite.

### 10. Read the whole decision back

```http
GET /api/v1/audit/entity/ALLOCATION/158
```

Every action against that record, chronologically: approved → accepted → conducted →
evaluated. This is what makes a decision reviewable a year later.

---

## Endpoints the frontend does not yet call

Built to specification, no client: `POST /auth/refresh`, `POST /auth/change-password`,
`/trainers/me/availability`, `/trainers/me/unavailability`, `/predictions/runs/*`,
`/allocations/{id}/mark-conducted`, `/allocations/{id}/withdraw`,
`/notifications/unread-count`, `/audit/export`, `/audit/entity/*`,
`/reports/{type}/export`, `/system/health/*`, and all of `/reference/*`.

`/auth/refresh` is the notable one — see the warning above.

## Parameters accepted and ignored

Three query parameters exist so the current frontend does not receive a 422, and are
discarded rather than honoured. They are marked `deprecated` in the OpenAPI schema.

| Parameter | Why it is ignored |
|---|---|
| `GET /dashboard/summary?role=` · `?userId=` | The caller would be declaring their own role. A Trainer requesting the Administrator dashboard receives the **Trainer** dashboard. |
| `GET /notifications?recipientId=` | Would let any signed-in user read anyone else's notifications by changing a number. |

See ADR-0012.
