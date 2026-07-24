# TPS Phase 1 — Database Engineering Progress

> Living plan per `02-DATABASE-PROMPT.md` §0. Checklist derived from §11.
> Items are ticked **as completed**. Notes are appended when a discovery changes the plan.

**Status:** ✅ Phase 1 complete. Halted at **STOP GATE 2** — awaiting human testing before Phase 2.

---

## 1. Task checklist (§11)

- [x] Read `frontend/src/types/domain.ts`, `frontend/src/mocks/`, `frontend/src/lib/scoring/`
- [x] Reconcile frontend types against §5; record any conflicts → **§3 below**
- [x] Print STOP GATE 1 setup commands; wait for confirmation — *passed, four extensions confirmed*
- [x] Scaffold `backend/` with uv, ruff, mypy, pytest
- [x] `app/core/config.py` and `app/db/` (base, session, naming convention, mixins)
- [x] `app/models/enums.py` — 17 `StrEnum`s, `CHECK` clauses generated from them
- [x] Reference models + Alembic revision — 10 tables
- [x] Identity models — `users`, `refresh_tokens`
- [x] Trainer models — 4 tables
- [x] Programme model
- [x] Scoring policy models
- [x] Prediction models — runs, predictions, exclusions
- [x] Allocation and evaluation models
- [x] System models — `audit_logs`, `notifications`
- [x] Hand-write revision 0002: `updated_at` trigger (23 tables), audit-immutability trigger, 3 registry sequences + function, deferred weight-sum trigger, `EXCLUDE` constraint
- [x] Hand-write revision 0003: `v_trainer_scoring_facts`
- [x] Verify `upgrade head` → empty autogenerate diff → `downgrade base` — *all three confirmed twice*
- [x] Deterministic seed generator, matched to the measured mock volumes
- [x] Seed the eight narrative fixtures (§7.4) — *asserted at seed time; the seed fails loudly if any is missing*
- [x] `scripts/reset.py` and `scripts/verify.py` — 30 checks
- [x] Data dictionary generator, ERD, **11** ADRs
- [x] Full quality-bar pass (§9)
- [x] STOP GATE 2 report

---

## 2. Host environment (probed, not assumed)

| Item | Found |
|---|---|
| PostgreSQL | **18.4** (Ubuntu 18.4-1.pgdg24.04+1), cluster `18/main`, **online**, port 5432 |
| `listen_addresses` | commented at `postgresql.conf:60` → effective default `localhost` — **must be changed** (§3.3) |
| `password_encryption` | commented at `postgresql.conf:97` → effective default `scram-sha-256` ✅ correct for PG18 |
| Config dir | `/etc/postgresql/18/main/` (`conf.d/` is empty) |
| Docker bridge | `docker0` = **172.17.0.1/16** — matches §3.3's expected address |
| Docker | 29.6.1 |
| uv | 0.11.25 |
| Python | 3.12.3 |
| `tps_db` / `tps_app` | Not yet verifiable without credentials — the human confirms at Gate 1 |

Nothing older than 14, so no §3.1 abort condition. All §5 features (`citext`, `pg_trgm`,
`btree_gist`, identity columns, partial unique indexes, constraint triggers) are available.

---

## 3. Frontend reconciliation — conflicts found (§2, §0.4)

The frontend contract was read in full and the mock generator was **executed** to measure real
volumes rather than trusting the prompt's stated figures. Twelve conflicts follow. Each states the
conflict, the recommendation, and whether it is blocking.

### C1 — Reference vocabularies disagree between §5.1 and `frontend/src/lib/constants.ts` 🟠

`02-DATABASE-PROMPT.md` §5.1 enumerates the **real** UPF reference data. The frontend mocks use
simplified/older lists. D9 ("seed mirrors the frontend mocks exactly") and §5.1 are in direct
tension.

| Vocabulary | §5.1 (this document) | Frontend `constants.ts` |
|---|---|---|
| Regions | 29 real policing regions (KMP East, Albertine North, Aswa West, …) | 7 broad labels (Kampala Metropolitan, Central, Eastern, Northern, Western, West Nile, Karamoja) |
| Directorates | 17 real directorates | 12, partly renamed (`ICT Research, Planning and Innovation`, `Community Affairs`, `Professional Standards Unit`, `Fire and Rescue Services`) |
| Stations | ~31 + 8 named training institutions | 29, shorter names (`Naguru` vs `Police Headquarters Naguru`; `Masindi` vs `Police Training School, Kabalye (Masindi)`) |
| Institutions | 22, grouped POLICE/UNIVERSITY/PROFESSIONAL/INTERNATIONAL | 13, names differ (`Police Training School Kabalye, Masindi`) |
| Specialisation areas | 24 | 24 — **identical** ✅ |

Every one of these is typed as plain `string` in `domain.ts`, so **no TypeScript contract breaks** —
only rendered literals differ.

**Recommendation:** seed the **real §5.1 lists**. They are explicitly enumerated, they are the
stated point of §7 ("withstand a Training Directorate officer reading it and recognising their own
organisation"), and the frontend's lists are a mock-era simplification. `constants.ts` becomes a
Phase-3 update. *Not blocking, but the human should confirm the direction.*

### C2 — `training_categories` is a different axis from the frontend's scoring category 🔴

This is the one **structural** gap, not a naming one.

- §5.1 `training_categories` seeds a **delivery-mode** taxonomy: Initial Training · Refresher ·
  Specialised Skills · Command and Leadership · Induction · Pre-Deployment · Regional/International ·
  Instructor Development.
- The frontend's `TrainingProgramme.category` carries a **subject** taxonomy: Investigations ·
  Forensics · Traffic · Community Policing · Public Order · Counter-Terrorism · Professional
  Standards · Child Protection · Marine · Intelligence · Firearms · Records Management.

The subject taxonomy is **load-bearing in the scoring engine**, in two places:

- `criteria.ts:71-76` — the SPECIALIZATION **+10 breadth bonus** fires when a second specialisation
  maps to the same programme category (`SPECIALIZATION_CATEGORY[area] === programme.category`).
- `generate.ts:542-543` — the PERFORMANCE **relevance test** counts an evaluation as relevant when
  its programme shares the current programme's category. This is what §5.10's view must express as
  "count of evaluations within the required specialisation".

If `training_categories` is seeded per §5.1 and nothing else changes, **both rules lose their
input** and Phase 2 cannot reproduce the frontend's scores.

**Recommendation (ADR-0008):** keep §5.1's `training_categories` exactly as specified, and add a
`discipline_group VARCHAR(60)` column to `specialization_areas` carrying the frontend's
`SPECIALIZATION_CATEGORY` value. A programme's subject group is then derived through
`required_specialization_area_id → discipline_group` — no new table, no change to §5.1's category
list, and both scoring rules keep a structurally enforceable input. `discipline_group` is NULL-safe
for `DRAFT` programmes, which have no requirement set yet and are never scored.

### C3 — §7.1's stated seed volumes do not match the mocks 🔴

The mock generator was executed. Measured against §7.1's claims:

| Entity | §7.1 claims | **Measured in mocks** | |
|---|---|---|---|
| Trainers | 812 | **812** | ✅ |
| Programmes | 46 | **46** | ✅ |
| Audit entries | ~600 | **600** | ✅ |
| Notifications | 18 | **18** | ✅ |
| Predictions | ~230 across runs | **3,828 across 40 runs** | ❌ |
| Allocations | 64 | **37** | ❌ |
| Evaluations | 47 | **42** | ❌ |

§7.1 also omits: 40 prediction runs, ~4,000 exclusion rows, 1,199 qualifications,
1,566 specialisations.

The "~230 predictions" figure appears to assume a top-N list per run. The mocks rank **every**
eligible trainer — the featured run alone produces 698 predictions and 114 exclusions from a pool
of 812.

**Recommendation:** honour the **measured** mock volumes, since D9 makes the mocks the contract and
§7.1's numbers are demonstrably stale. Store all predictions and exclusions — ~3,800 and ~4,000 rows
is nothing for PostgreSQL, and truncating to a top-N would break the Exclusion Ledger, which is the
table §5.6 calls the most under-appreciated in the schema. Allocation count rises above 37 anyway
once fixture §7.4.6 is seeded (see C12).

### C4 — `PredictionRun.runId` is `string` in the frontend; D3 mandates `BIGINT` 🟢

`domain.ts:171` types `runId: string`; the mock uses `RUN-{programmeId}-{iso}`. Every other
identifier is `number`.

**Recommendation:** honour D3 — `run_id BIGINT`. Phase 2 serialises it as a string in the DTO, which
satisfies the existing type with no frontend change. Noted for the Phase 2 schema layer.

### C5 — Two frontend `Allocation` fields are missing from §5.7 🟢

`domain.ts:200-202` requires:

- `frozenRationale: string` — "the rationale as it stood at approval — shown to the trainer (§11.7)"
- `weightsWereSimulated: boolean` — also present in `ApproveAllocationInput` (`api.ts:73`)

Neither appears in §5.7's `allocations` column list, yet both are part of the frozen Decision
Receipt that §5.7's own rationale argues for.

**Recommendation:** add `frozen_rationale TEXT NOT NULL` and
`weights_were_simulated BOOLEAN NOT NULL DEFAULT FALSE`. Consistent with the section's intent.

### C6 — `Trainer.profileCompleteness` is missing from §5.3 and drives confidence 🟠

`score.ts:77-79` weights it at **0.35** of the confidence level, which sets the LOW/MODERATE/HIGH
band shown throughout the UI. §5.3's `trainers` table has no such column, and it is not derivable
from the other seeded columns in the way the mock uses it (the mock assigns it randomly).

**Recommendation:** store `profile_completeness SMALLINT NOT NULL DEFAULT 0 CHECK (0..100)` on
`trainers`, seeded to the mock's values so confidence bands reproduce exactly. Document it as a
deliberately denormalised derived value, maintained by Phase 2 on profile write, with the derivation
rule (presence of bio, contact, enlistment date, ≥1 qualification, ≥1 specialisation) recorded in the
data dictionary.

### C7 — Demo password differs 🟢

§7.5 specifies `Tps@2026#Demo`. The frontend hard-codes `DEMO_PASSWORD = 'Demo@2026'` at
`frontend/src/hooks/useAuth.ts:16` and `generate.ts:94`.

**Recommendation:** seed §7.5's `Tps@2026#Demo` (authoritative and stronger). This makes
`useAuth.ts:16` a **one-line Phase-3 change**; flagged so it is not discovered at demo time.

### C8 — Audit-action and rank vocabularies are DB supersets 🟢

- §5.8 adds `TOKEN_REFRESHED`, `PROFILE_UPDATED`, `AVAILABILITY_CHANGED`; the frontend `AuditAction`
  union (`domain.ts:221-243`) lacks all three. A Phase-2 response carrying one would not type-check.
- §5.1 seeds 15 ranks; the frontend `PoliceRank` union (`domain.ts:18`) has 9 — no `SPC`, `CP`,
  `SCP`, `AIGP`, `DIGP`, `IGP`.

**Recommendation:** seed the full §5.1 and §5.8 sets (the ladder and the action list should be
complete in the database), but **constrain every seeded person to the 9 ranks the frontend knows**,
so no seeded row can break the contract. The three missing audit actions are a Phase-3 union
addition; none of them is produced by the seed.

### C9 — The mocks have no `users` rows for trainers 🟠

`generate.ts:181` sets `Trainer.userId = 1000 + trainerId` for all 812 trainers, but the mock
`users[]` array contains only 40 rows (ids 1–40, plus the demo `trainer` at 1001). The database
requires `trainers.user_id` **UNIQUE NOT NULL** with a `RESTRICT` FK, so those users must exist.

**Recommendation:** seed **~851 users** — 812 trainer accounts (one per trainer, preserving the
`1000 + trainer_id` numbering so mock links survive) plus ~39 non-trainer staff accounts. This is an
expansion the relational model forces; it does not change anything the frontend renders.

### C10 — `trainer_unavailability` has no frontend counterpart 🟢

§5.3 introduces the table; the frontend has no equivalent entity. Fixture §7.4.3 explicitly requires
a row corroborating the declined allocation ("Committed to court testimony in Jinja for the same
period"), which the mocks carry only as a bare string.

**Recommendation:** build the table and seed it. This is an intentional improvement over the mocks,
not a conflict. Also implement the §5.3 `EXCLUDE USING gist` non-overlap constraint — the seed
generates windows per trainer sequentially, so non-overlap is free.

### C11 — Fixture §7.4.1's stated gap is already satisfied, but tighter than described 🟢

§7.4.1 asks for ranks 1 and 2 "within 1.4 points of each other". Measured featured run
(programme 1, *Basic Cybercrime Investigation Course — Intake 14*): **rank 1 = 90.1, rank 2 = 89.6,
gap 0.5**. Within tolerance; no change needed. Also verified against §7.4:

| Fixture | Status in mocks |
|---|---|
| 1 · tight top two | ✅ gap 0.5 |
| 2 · zero-evaluation LOW-confidence trainer in top five | ✅ two of them (ranks 3 and 5, confidence 27 and 33) |
| 3 · declined allocation with reason | ✅ string present — ⚠️ needs the new corroborating unavailability row |
| 4 · `CONDUCTED` not `EVALUATED` | ✅ 2 programmes |
| 5 · ≥8 unavailable, ≥5 missing specialisation | ✅ far exceeded — 62 and 52 in the featured run |
| 6 · one trainer allocated 4× in six months | ❌ **absent** — see C12 |
| 7 · several `EVALUATED` across ≥4 quarters | ✅ 30 programmes |
| 8 · `LOGIN_FAILED` entries and one `ACCOUNT_LOCKED` | ⚠️ `LOGIN_FAILED` present; **`ACCOUNT_LOCKED` absent** from the mock action pool |

### C12 — Two §7.4 fixtures must be engineered, not copied 🟠

The mocks allocate exactly one trainer per qualifying programme — the run's top candidate — so:

- **Fixture 6** (one trainer allocated 4× in six months while equally-qualified peers have none, the
  over-reliance pattern the SRS problem statement names) does not occur.
- **Fixture 8**'s `ACCOUNT_LOCKED` entry is not in the mock's `actionPool` (`generate.ts:702-709`).

**Recommendation:** seed both deliberately on top of the mock-derived data. Fixture 6 is the pattern
the whole system exists to expose; the utilisation chart is empty without it.

---

## 4. Open questions — **resolved 2026-07-23**

All three were put to the human before any code was written. Decisions:

1. **C1 — reference vocabularies: real §5.1 UPF lists win.** ✅ *Decided.*
   Seed the 29 real policing regions, 17 directorates, and full station/institution names.
   `frontend/src/lib/constants.ts` is updated in Phase 3. Safe because `domain.ts` types every one
   of these as plain `string` — only rendered literals change. Deviation from D9 is deliberate and
   recorded in **ADR-0009**.
2. **C3 — measured mock volumes win over §7.1's stated figures.** ✅ *Decided.*
   Store every prediction (~3,828) and every exclusion (~4,000) across all 40 runs. No top-N
   truncation: a truncated Exclusion Ledger cannot answer "why isn't so-and-so on the list?", which
   is the SRS problem statement. Recorded in **ADR-0010**.
3. **C7 — seed `Tps@2026#Demo` per §7.5.** ✅ *Decided.*
   `frontend/src/hooks/useAuth.ts:16` needs a one-line change in Phase 3. Carried into the STOP
   GATE 2 report so it is not discovered mid-demo.

Consequential follow-ups accepted with these decisions:

- **C2** — `discipline_group` on `specialization_areas` (ADR-0008), since §5.1's
  `training_categories` cannot feed the two scoring rules that need a subject taxonomy.
- **C5** — add `frozen_rationale` and `weights_were_simulated` to `allocations`.
- **C6** — store `profile_completeness` on `trainers`.
- **C9** — seed ~851 users, not 40, because `trainers.user_id` is a `RESTRICT` FK.
- **C12** — engineer fixtures §7.4.6 (over-reliance pattern) and §7.4.8 (`ACCOUNT_LOCKED`), absent
  from the mocks.

---

## 5. ADRs planned

The seven required by §6, plus one forced by C2:

| ADR | Title | Source |
|---|---|---|
| 0001 | ORM-first schema authority | D1 |
| 0002 | Integer primary keys | D3 |
| 0003 | `NUMERIC`, not float, for scores | D4 |
| 0004 | Lookup tables over native enums | §4, §5.1 |
| 0005 | Database-enforced audit immutability | D6 |
| 0006 | Frozen allocation snapshot | D7, §5.7 |
| 0007 | View, not materialized view | §5.10 |
| **0008** | **Discipline group on specialisation areas** | **C2 — new** |
| **0009** | **Real UPF reference data over mock-mirrored lists** | **C1 — new, deviates from D9** |
| **0010** | **Full prediction and exclusion history, no top-N truncation** | **C3 — new** |

---

## 6. Change log

| Date | Note |
|---|---|
| 2026-07-23 | Plan created. Frontend contract read in full; mock generator executed to measure real volumes. Twelve conflicts recorded (§3). Host environment probed (§2). Halted at STOP GATE 1. |
| 2026-07-23 | Three open questions resolved by the human (§4). ADR list grows from 7 to 10. Still halted at STOP GATE 1 pending `\dx` confirmation. |
| 2026-07-23 | Gate 1 passed. Built the full persistence layer: 26 tables, 3 migrations, seed, reset, verify, docs. See §7 for the outcome. Halted at STOP GATE 2. |


---

## 7. Outcome

### Delivered

| Item | Result |
|---|---|
| Tables | **26** (+ 1 view), matching §5 exactly |
| Migrations | 3 — one autogenerated and hand-reviewed, two hand-written |
| `alembic upgrade head` on an empty database | ✅ clean |
| `alembic downgrade base` | ✅ clean, leaves only `alembic_version` |
| Autogenerate drift after `upgrade head` | ✅ **empty** |
| Seed | **37,831 rows in 16.3 s** (budget: 60 s), idempotent |
| Narrative fixtures (§7.4) | **8 / 8**, asserted at seed time |
| `scripts/verify.py` | **30 / 30 checks pass** |
| `pytest` | **12 / 12 pass** |
| `ruff check` + `ruff format --check` | ✅ clean |
| `mypy --strict` | ✅ clean on `app/`, `scripts/`, `data/` (28 files) — §9 required `app/models/` only |
| ADRs | **11** (the 7 required, plus 0008–0010 from conflicts and 0011 for the weight-sum guarantee) |

### Seeded volumes

| Entity | Rows |
|---|---|
| Users | 854 |
| Trainers | 812 |
| Trainer qualifications | 1,186 |
| Trainer specialisations | 1,641 |
| Trainer unavailability | 53 |
| Training programmes | 46 |
| Prediction runs | 40 |
| Predictions | 7,327 |
| Prediction exclusions | 25,153 |
| Allocations | 55 |
| Performance evaluations | 46 |
| Audit entries | 600 |
| Notifications | 18 |

### Deviations from the specification

Each is recorded as an ADR with alternatives considered.

1. **ADR-0009 — real UPF reference data instead of the frontend's mock lists.** A
   deliberate deviation from **D9**, confirmed by the project owner. No TypeScript
   contract breaks; `frontend/src/lib/constants.ts` needs updating in Phase 3.
2. **ADR-0010 — measured mock volumes instead of §7.1's stated figures**, which are
   wrong for predictions, allocations, and evaluations.
3. **ADR-0008 — `discipline_group` added to `specialization_areas`.** Forced: §5.1's
   `training_categories` cannot feed the two scoring rules that need a subject
   taxonomy.
4. **Two columns added to `allocations`** (`frozen_rationale`, `weights_were_simulated`)
   — required by `domain.ts`, absent from §5.7.
5. **`profile_completeness` added to `trainers`** — contributes 35% of the confidence
   level, absent from §5.3.
6. **`searchable_name` added to `trainers`** — a GIN trigram index cannot span a join;
   documented as the one intentional duplication in the trainer tables.
7. **`random.Random(20260722)` per §7.1, not a port of the frontend's mulberry32.**
   Row-level values therefore differ from the mocks; volumes and fixtures match.
8. **Demo password `Tps@2026#Demo` per §7.5**, differing from the frontend's
   hard-coded `Demo@2026` at `useAuth.ts:16`.
9. **Non-demo accounts have no usable password.** Hashing 850 accounts with the
   configured Argon2id parameters costs 220 s (measured), which alone would breach the
   60-second seed budget.

### Known limits, stated rather than glossed

- **The audit trigger does not block `TRUNCATE`** (ADR-0005). It guards row-level
  `UPDATE` and `DELETE`; `TRUNCATE` requires table ownership and is how
  `scripts/reset.py` works.
- **The weight-sum trigger permits a policy with no weights at all** (ADR-0011), and
  does not require all five criteria to be present. Phase 2's service layer must
  enforce completeness before activation.

### For Phase 2

- Paginate `predictions` and `prediction_exclusions`. A single run holds 698 ranked
  candidates.
- Construct the Argon2id verifier from `app/core/config.py` settings, not from
  hard-coded parameters, or every seeded demo account will fail to authenticate.
- Re-implement the scoring engine in `app/services/` against the specification.
  `data/seed_source/scoring.py` is a seed-only port and deliberately not shared — if
  the two disagree, that disagreement is a finding.
- Maintain `trainers.searchable_name` and `trainers.profile_completeness` on profile
  write.

---
---

# PHASE 2 — BACKEND API

> Per `03-BACKEND-PROMPT.md` §0 and §16. Halted at Phase 2 **STOP GATE 1** after Stage 1.

## P2.1 Checklist (§16)

- [x] Read `frontend/src/api/endpoints/`, `types/domain.ts`, `lib/scoring/`, `mocks/handlers.ts`
- [x] Reconcile every frontend call against §6; log conflicts before writing code → **§P2.2**
- [ ] Stage 1: foundation, middleware, health, Docker, host-DB connectivity
- [ ] 🛑 STOP GATE 1 — human verifies `/health/ready` and a successful login
- [ ] Stage 2: auth, lockout, refresh rotation, RBAC dependency, audit service
- [ ] Stage 3: reference, trainers, programmes read paths, pagination pattern
- [ ] Stage 4: prediction engine — gates, criteria, shrinkage, confidence, ranking, narrative
- [ ] Stage 4: unit suite at 100% coverage, determinism test passing
- [ ] Stage 5: programme write paths, predict, simulate, scoring policy
- [ ] Stage 6: allocations, freezing, promote-next, trainer responses, evaluations, notifications
- [ ] Stage 7: users, roles, audit, dashboard, reports, system health
- [ ] Stage 8: authorisation test matrix, rate limiting, mypy strict, lint
- [ ] `docs/ALGORITHMS.md` (all twelve sections)
- [ ] README, ARCHITECTURE, API-GUIDE, ADRs, exported `openapi.json`
- [ ] Frontend cut-over: `VITE_USE_MOCKS=false`, verify visual parity, list any differences
- [ ] 🛑 STOP GATE 2 — full report

## P2.2 Frontend ↔ §6 reconciliation — 14 mismatches

`03-BACKEND-PROMPT.md` contains an internal contradiction:

- **§13** — "Endpoint paths or field names that do not match `frontend/src/api/endpoints/`. The
  contract is not negotiable and a mismatch is not a 'minor fix'."
- **§6** — "BUILD EVERY ONE", then specifies paths that differ from the frontend in 14 places.

Both cannot be satisfied as written. Every difference is listed below.

### Group A — cosmetic differences (path or method only, same semantics)

| # | Frontend calls | §6 specifies | Difference |
|---|---|---|---|
| A1 | `POST /programmes/{id}/requirements` | `PUT /programmes/{id}/requirements` | method |
| A2 | `GET /programmes/{id}/eligibility` | `GET /programmes/{id}/eligibility-preview` | path |
| A3 | `POST /scoring-policy` | `PUT /scoring-policy` | method |
| A4 | `GET /reports/allocations` | `GET /reports/allocation-history` | path |
| A5 | `GET /reports/performance` | `GET /reports/performance-trends` | path |
| A6 | `GET /trainers/{id}/evaluations` | `GET /evaluations/trainer/{trainerId}` | path |
| A7 | `POST /allocations/{id}/accept` · `/decline` | `POST /trainers/me/assignments/{id}/accept` · `/decline` | path |
| A8 | `GET /dashboard?role=` | `GET /dashboard/summary` | path |

These are safe to satisfy **both ways**: implement §6's path as canonical and register the
frontend's path as an alias on the same handler. No semantic compromise.

### Group B — the frontend's design is insecure and must not be preserved 🔴

| # | Frontend calls | Problem |
|---|---|---|
| B1 | `GET /me/trainer?userId=<id>` | Identity from a **query parameter**. Any authenticated user can read any trainer's profile by changing the number. Textbook IDOR (OWASP Broken Object Level Authorization). §6.3 correctly specifies `GET /trainers/me`, taking identity from the token. |
| B2 | `PATCH /trainers/{id}` for self-update | Same class: the trainer's own id is supplied by the client. §6.3 specifies `PATCH /trainers/me`. |
| B3 | `GET /dashboard?role=<role>&userId=<id>` | **The caller declares their own role.** A Trainer can request the Administrator dashboard. §6.13 derives the role from the token. |
| B4 | `GET /notifications?recipientId=<id>` | Read another user's notifications by changing the id. §6.12 scopes to the caller. |

**These four will not be aliased.** Building them as the frontend currently calls them would ship
four authorisation bypasses into a government system. §6 is right and the frontend is wrong; the
four call sites are corrected in Phase 3. This is exactly the case §0 anticipates when it says a
mismatch must be raised rather than silently resolved.

### Group C — shape differences requiring a decision

| # | Frontend expects | §6 specifies | Resolution |
|---|---|---|---|
| C1 | `PATCH /trainers/{id}/credentials` — full qualification + specialisation lists in one body | Granular `POST/PATCH/DELETE /trainers/me/qualifications` and `/specializations` | Build §6's granular routes (they support the object-level ownership checks §7.1 demands). Also provide the bulk route on `/trainers/me/credentials`, since replacing a list wholesale is a legitimate operation the UI already performs. |
| C2 | `GET /users` → bare `User[]` | §4.1 mandates the paginated envelope on every list | Return the envelope. 40-odd users today, but "every list endpoint, no variations" is the rule and an unpaginated list is a latent problem. Frontend adapts in Phase 3. |
| C3 | `GET /notifications` → bare `Notification[]` | §4.1 envelope | Same as C2. |
| C4 | `GET /audit` → offset `Paginated` with `page`/`total` | §6.11 requires **keyset** pagination | Support both: keyset via `?after=` (the documented path, used by export and deep paging) and offset for the frontend's current table. Offset is capped at 10,000 rows, beyond which keyset is required. |
| C5 | Weight Studio simulates **client-side** (`recomputeWithWeights`) | §6.5 `POST /predictions/simulate` | Build the endpoint. Client-side simulation is why §5.8 warns the preview can silently diverge from the server. Frontend switches to it in Phase 3. |

### Group D — §6 endpoints the frontend never calls

Built as specified; they have no client yet. `POST /auth/refresh`, `GET /auth/me`,
`POST /auth/change-password`, `/trainers/me/availability`, `/trainers/me/unavailability`,
`/trainers/me/assignments`, `/trainers/me/performance`, `/predictions/runs/*`,
`/allocations/{id}/mark-conducted`, `/allocations/{id}/withdraw`, `/users/{id}/deactivate`,
`/users/{id}/reset-password`, `/notifications/unread-count`, `/audit/export`,
`/audit/entity/{type}/{id}`, `/reports/{type}/export`, `/system/*`, all of `/reference/*`.

`/auth/refresh` is notable: the frontend currently has **no refresh flow at all** — its axios
interceptor simply redirects to sign-in on 401. With a 15-minute access token that logs the user out
every 15 minutes. Phase 3 must add the refresh call.

### Decision taken

Build **§6 as canonical**, add **Group A aliases** so the frontend keeps working unchanged, and
**refuse Group B** — those four are corrected in the frontend rather than reproduced in the API.
Recorded as ADR-0012.

## P2.3 Stage 1 — complete, verified in-process

| Component | State |
|---|---|
| `app/core/` | config (JWT/CORS/rate-limit settings), security (Argon2 + JWT), exceptions, problem_details (RFC 9457), logging (structlog + redaction), clock (injectable), pagination (offset + keyset) |
| `app/middleware/` | correlation id, request logging, audit context |
| `app/schemas/` | `base.py` (CamelModel, Decimal serialisers), `auth.py`, `reference.py` |
| `app/api/` | `deps.py` (DbSession, CurrentUser, require_roles, object-level check), `router.py`, `v1/auth.py`, `v1/system.py` |
| `app/services/` | `audit_service.py`, `auth_service.py` |
| `app/repositories/` | `reference_repo.py` |
| Docker | `Dockerfile` (multi-stage, non-root, healthcheck), `.dockerignore`, `docker-compose.yml` |

**Verified against the live database (in-process, via ASGITransport):**

- `/health/live`, `/health/ready` (database reachable), `/version` → 200
- All four demo accounts sign in with `Tps@2026#Demo` — **B6 confirmed**: Phase 2's Argon2
  verifier matches Phase 1's seeded hashes
- `trainer` resolves `trainerId=1` (Sarah Mugisha) through the outer join
- `/auth/me` with a bearer token → 200; unauthenticated → 401 `application/problem+json`
- **FR-01 lockout**: attempts 1–2 → 401 with `attemptsRemaining`; attempt 3 → 423 with
  `retryAfterSeconds=900`; the correct password is then rejected while locked
- **B5 refresh rotation**: rotate → 200; replay the old token → 401 **and the whole family is
  revoked**, so the legitimately-issued newer token is dead too
- `ruff check` + `ruff format --check` clean; `mypy --strict` clean on 43 files

### Bug found and fixed during Stage 1

The FR-01 lockout counter never persisted. Every failed sign-in raises, the request-scoped
session rolls back on any exception, and the `failed_login_count` increment plus the
`LOGIN_FAILED` audit entry were discarded with it — so the account never locked, however many
times it was attacked. Fixed with `AuthService._persist_then_raise`, which commits the failure
bookkeeping before raising. This is the one place a **rejected** request must still write, and
it is confined to one visible helper rather than weakening the session dependency's rollback.

### Blocked: container build (environment, not code)

`docker compose build` cannot complete on this machine. Diagnosis:

| Check | Result |
|---|---|
| `getent hosts pypi.org` | returns **IPv6 only** |
| `curl -6 https://pypi.org` | fails instantly — no IPv6 route |
| `curl -4 https://pypi.org` | **200 in 1.08 s** |
| `/etc/docker/daemon.json` | absent — Docker inherits the broken resolver |

Docker's builder receives AAAA records, attempts IPv6, and either stalls (a 550-second pip read
timeout) or fails DNS outright (`lookup auth.docker.io: server misbehaving`). Host tooling works
because it falls back to IPv4; Docker's embedded resolver does not.

Two Dockerfile changes were made in response and are worth keeping regardless:

1. Dropped `# syntax=docker/dockerfile:1` and `COPY --from=ghcr.io/astral-sh/uv` — both pull
   images from external registries at build time, making a local build depend on two registries
   beyond Docker Hub. uv now installs from PyPI.
2. Added `PIP_DEFAULT_TIMEOUT=300`, `PIP_RETRIES=20`, `UV_HTTP_TIMEOUT=300`, so a constrained
   link produces a slow build rather than a failed one.

**The remedy is host-side** and is recorded in the STOP GATE 1 report.

### Container build — three environment faults found

None is a code defect. All three are on the host.

**1. IPv6 DNS with no IPv6 route.** `getent hosts pypi.org` returns AAAA records only;
`curl -6` fails instantly while `curl -4` returns 200 in ~1 s. Docker's embedded resolver has no
IPv4 fallback, so the builder stalls or fails DNS outright.
*Remedy:* `/etc/docker/daemon.json` with `{"dns": ["8.8.8.8", "1.1.1.1"]}`, then restart Docker.

**2. Throughput of roughly 24 kB/s to PyPI from inside the builder.** `pip install uv` took 266 s
and `uv sync` then timed out on `asyncpg` even with `UV_HTTP_TIMEOUT=300`.
*Remedy:* build a wheelhouse on the host, where the network works, and install offline in the
image. `requirements.txt` is exported from `uv.lock` with hashes, so the lockfile remains the
source of truth.

**3. Port 8000 is already bound** by an unrelated project's container
(`ai-vs-human-data-collection-tool-backend-1`). `docker compose up` would have failed on the port
mapping regardless of the build.
*Remedy:* the Compose port is now `${API_PORT:-8000}:8000`, so the host port can be changed
without editing the file.

### Stage 1 verified over real HTTP, without Docker

The API does not need a container to run, and Stages 2–8 do not depend on one. Running
`uvicorn` directly on the host:

```
GET  /health/ready  → 200  postgresql healthy, 6.95 ms
POST /api/v1/auth/login → 200  Grace Nabirye · TRAINING_ADMINISTRATOR · JWT issued
```

Containerisation (B11) remains a deliverable and the Dockerfile, Compose file, and wheelhouse
approach are all in place; only the image build is outstanding, and it is blocked on host
networking rather than on anything in this repository.

## P2.4 Stage 4a — prediction engine complete

The core of the system. Pure Python: no database session, no HTTP, no clock reading.
Everything arrives as arguments, which is what makes 100% coverage affordable and what lets
the Weight Studio's simulation reuse the identical code path (§5.8).

| Module | Responsibility |
|---|---|
| `types.py` | Frozen dataclasses — `CandidateFacts`, `CriterionScore`, `Exclusion`, `ScoredCandidate`, `PredictionRunResult` |
| `gates.py` | BR-03, BR-04, FR-05 in fixed precedence order; officer-readable exclusion sentences |
| `criteria.py` | Five criterion classes behind a `Criterion` protocol, in a registry keyed by `CriterionKey` |
| `confidence.py` | Exponential recency decay, 18-month half-life, floored at 40 |
| `narrative.py` | Rationale, and exhaustive counterfactual search over three levers |
| `engine.py` | Orchestration: gate → score → rank → narrate |

**Quality gates met**

- `pytest tests/unit/` — **77 passed**
- **100% coverage on `app/services/prediction/`** (§10's requirement)
- `ruff check` and `ruff format --check` clean
- `mypy --strict` clean on 51 source files
- **B7**: no `services/` module imports `fastapi` — verified by grep
- **B10**: no `float` arithmetic in `services/prediction/` — the only `float()` call is
  `CriterionScore.to_json`, at the JSONB boundary, after the value has been quantised while
  still exact. The module docstring was corrected when it overclaimed otherwise.

**Dead code found and removed.** The counterfactual had a branch emitting *"would rank 1st with
one further recorded evaluation"* without naming a threshold. It is unreachable: the minimum
possible rating (1.0) can never *raise* a mean that already blends in the prior, so the branch
could only fire on a gap of zero, which the function returns early on. Removed rather than
covered with a contorted test — a sentence that cannot occur is worse than no sentence, because
it invites a reader to assume it can.

**NFR-10 discharged structurally.** Adding a sixth criterion means adding a class to
`criteria.py` and a row to `scoring_policy_weights`. No migration, no change to `engine.py`.

## P2.5 Stage 4b — the facts query (§5.2)

One round trip, one row per trainer, feeding the engine.

### Performance: 995 ms → 62 ms

The budget is 150 ms for 812 trainers. Three rounds of work:

| Version | Warm time | What changed |
|---|---|---|
| Correlated `LATERAL` per fact, reading `v_trainer_scoring_facts` | **419 ms** | first attempt |
| Same, but computing only the needed discipline instead of the view's JSONB map | 350 ms | dropped the view from this path |
| **Eight pre-aggregated CTEs, hash-joined once** | **62–83 ms** | set-based instead of 6,496 nested-loop iterations |

`EXPLAIN (ANALYZE, BUFFERS)` showed the cost was structural, not a missing index: every
per-loop node was already sub-millisecond, but there were eight of them per trainer. The
rewrite scans each table once and joins on `trainer_id`.

Two secondary findings:

1. **`v_trainer_scoring_facts` returned a wrong per-group count.** Its
   `evaluations_by_discipline_group` map reported 1 evaluation where the trainer had 6. The
   nested window function inside its `LATERAL` partitions per row rather than per group. The
   facts query no longer depends on it; **the view still needs fixing for the dashboard and
   reports**, which is logged for Stage 7.
2. **asyncpg could not infer parameter types** for `:param IS NOT NULL` and required explicit
   `CAST(... AS text)`. Without them the query failed with `AmbiguousParameterError`.

### End-to-end against real seeded data

```
facts query + engine : 182-200 ms   (NFR-01 ceiling: 10 000 ms)
ranked               : 704
excluded             : 108  — 54 MISSING_SPECIALIZATION, 52 UNAVAILABLE, 2 SCHEDULE_CONFLICT
```

### A consequence of §5.5 worth stating plainly

The shrinkage prior is *the mean of every evaluation in the system*, which in the seeded data
is **4.45** — the seeded ratings skew high. A trainer with **no** evaluations therefore scores
about 86/100 on PERFORMANCE, ahead of a trainer with a genuine 4.0 average.

That is correct empirical-Bayes behaviour — "no data, assume average", and the average really
is 4.45 — and it is exactly what §5.5 specifies. It is also why the top-ranked candidate in the
featured run carries **LOW confidence**. The confidence band is the safeguard against exactly
this, and it is working: the officer sees rank 1 flagged as thinly evidenced.

Worth revisiting only if real UPF evaluation data proves less generous than the seed.

### Bug fixed

The proficiency counterfactual read *"a higher recorded proficiency in Advanced"* — naming the
trainer's current level instead of the discipline. Now: *"...in Cybercrime Investigation"*.
Ranks 3 and 4 correctly return `None`, since no single change closes their gap.

## P2.6 Stage 3 — reference and trainer read paths

| Endpoint | Access | Verified |
|---|---|---|
| `GET /reference/all` + 9 individual lists | any authenticated | 10 lists in one round trip, `Cache-Control: max-age=300` |
| `GET /trainers` | TA·TO·SA | 812 total, 271 pages, projection not hydration |
| `GET /trainers/me` and `/me/*` | TR | identity from the **token**, never a query parameter |
| `PATCH /trainers/me`, `/me/availability` | TR | blank contact/rank/station → 422 naming the field |
| `GET/POST/DELETE /me/qualifications`, `/me/specializations`, `/me/unavailability` | TR (owner) | POST appends; duplicate discipline → 409, never a silent update |
| `GET /trainers/{id}`, `/{id}/evaluations` | TA·TO·SA·TR(self) | object-level check enforced |

**Both authorisation layers confirmed working against the live database:**

```
GET /trainers          as TRAINER      -> 403   (role gate)
GET /trainers/2        as TRAINER id=1 -> 403   (object-level gate)
GET /trainers/1        as TRAINER id=1 -> 200   (own record)
```

**Sort allowlist rejects injection:**

```
?sortBy=force_number;DROP TABLE users
-> 422 "Cannot sort by '...'. Allowed: availabilityStatus, forceNumber, ..."
```

`sortBy` is an identifier, not a value, so it cannot be parameterised. The allowlist is the
defence, and it is exercised.

### Three defects found and fixed

1. **`PageParams` as `Annotated[..., Query()]` rejected every request** with
   *"field required: params"*. FastAPI treats a Pydantic model under `Query()` as one scalar
   parameter; `Depends()` makes it expose each field as its own query parameter. Every list
   endpoint would have been unusable.
2. **`TrainerService` read the wall clock** via `datetime.date.today()`, breaking §14.1's
   "never call `datetime.now()` inside a service" — the two rules that depend on it ("is this
   course still running?", "is this year in the future?") would have been untestable. Now takes
   an injected `Clock`. Caught by ruff's `DTZ011`.
3. **`sum(...) / len(...)` over ratings returned `Decimal | float`**, which would have put a
   float on an auditable number (B10). Pinned via a typed helper.

## P2.7 Stage 5 — programmes, prediction, simulation, scoring policy

Verified end to end over HTTP against the live database.

```
1. FR-04 create           201  TPS/REQ/2026/0048  status=DRAFT  requiredSpecialization=None
2. predict too early      409  rule=FR-05  "no required specialisation yet"
3. FR-05 requirements     200  status=REQUIREMENTS_SET  Cybercrime Investigation, 5y, Bachelor's
4. eligibility preview    200  "452 of 812 trainers meet these criteria"
5. FR-06 predict          201  runId=41 ranked=452 excluded=360 pool=812 elapsed=209ms
6. Exclusion Ledger       228 BELOW_MINIMUM_QUALIFICATION [FR-05]
                           54 MISSING_SPECIALIZATION      [BR-04]
                           52 UNAVAILABLE                 [BR-03]
                           26 BELOW_MINIMUM_EXPERIENCE    [FR-05]
7. Weight Studio          200  persisted=false, runId=null, rank deltas up to +84 places
8. weights must total 100 422  "Weights must total 100, but they total 105."
9. simulate as TO         403
10. PUT policy as TA      403  (System Administrator only)
```

**The Score Ledger adds up**: five criterion contributions summing to exactly the stored
`predictionScore` (96.24), in `Decimal` throughout. An officer can check it by hand, which is
the entire justification for choosing an additive model over something more sophisticated.

**Exclusion reasons read as sentences**, not codes: *"Highest qualification is certificate;
bachelor's degree required."*, *"4 years of service; 5 required."*

**Simulation shares the engine.** `POST /predictions/simulate` and
`POST /programmes/{id}/predict` call the same `generate_prediction`; only the caller decides
whether to write. The simulation's sole write is a `WEIGHTS_SIMULATED` audit entry, because who
explored which weightings before approving is itself part of the decision record.

### Group A path aliases implemented

The frontend's paths are served alongside §6's canonical ones, hidden from the OpenAPI schema so
the documented surface stays clean:

| Frontend calls | Canonical | Both work |
|---|---|---|
| `POST /programmes/{id}/requirements` | `PUT` | ✅ |
| `GET /programmes/{id}/eligibility` | `/eligibility-preview` | ✅ |
| `POST /scoring-policy` | `PUT` | ✅ |

### Defect found in the test harness, not the code

A shell variable captured multi-line output, producing `POST /api/v1/programmes/` with an empty
id and a 307 redirect loop. The verification harness is now a Python script
(`scratchpad/spine.py`) rather than shell interpolation.

## P2.8 Stage 6 — the allocation lifecycle

FR-08, FR-09, FR-10, BR-02, BR-06, BR-07. This is the stage where the system stops describing and
starts deciding, so the design notes below matter more than the endpoint list.

| Component | State |
|---|---|
| `app/schemas/` | `allocation.py` (receipt, approve/decline/withdraw inputs, promote-next response, assignments), `evaluation.py`, `notification.py` |
| `app/services/` | `allocation_service.py`, `evaluation_service.py`, `notification_service.py` |
| `app/api/v1/` | `allocations.py` (+ `assignments_router` for §6.3), `evaluations.py`, `notifications.py` |
| Tests | `tests/integration/test_allocation_flow.py` — 15 tests, plus `conftest.py` |

### Decisions taken in this stage

**The frozen snapshot is written in exactly one place.** `AllocationService._create_allocation`
is the only code that sets `frozen_score`, `frozen_rank_position`, `frozen_breakdown`,
`frozen_weights` and `frozen_rationale`. Nothing recomputes them on read. That makes "the receipt
is never re-derived" a property of the code rather than a habit that survives until someone adds
a convenience method.

**`weights` and `weightsWereSimulated` in the approve body are ignored.** The frontend's
`ApproveAllocationInput` sends both. Freezing client-supplied weights onto a government decision
record would let the receipt be made to say anything, so `frozen_weights` always comes from the
run's `weights_snapshot` and `weights_were_simulated` is derived from
`run.weights_are_policy_default`. The fields stay in the schema, marked deprecated, so the
existing frontend body does not 422.

**`programmeId` and `trainerId` are consistency checks, not inputs.** Both are derivable from the
prediction. When supplied they must agree with it — a disagreement means the screen the operator
is approving from is not showing what the server is about to record, which is worth a 409.

**The gates are re-checked against live data, through the engine's own query.**
`TrainerRepository.fetch_scoring_facts` gained a `trainer_ids` filter so the approval path calls
the *same* SQL and the *same* `evaluate_gates` as the ranking did. A second, hand-written
re-check would drift, and the drift would show up as an approval admitting someone the ranking
excluded. Cost: one facts query (~60 ms) per approval, paid to keep one source of truth.

**A programme holds one live allocation.** `PENDING_TRAINER`, `CONFIRMED`, `CONDUCTED` and
`EVALUATED` all occupy it; `DECLINED` and `WITHDRAWN` release it. Enforced under
`SELECT ... FOR UPDATE` on the programme row, so two administrators approving different
candidates in the same second cannot both pass the check and both insert.

**A decline returns the programme to `PREDICTED`, not `AWAITING_RESPONSE`.** §6.7 does not say;
leaving it awaiting a response nobody will give is wrong, and the ranking still stands, so the
next candidate can be promoted without a re-run. Same for a withdrawal.

**Accepting sets the trainer `ASSIGNED`; evaluating releases them to `AVAILABLE`.** The scoring
consequence is the point — the AVAILABILITY criterion caps an assigned trainer at 50, so the
system stops favouring someone already committed, and starts again when the course is closed.

**Notifications: created in-transaction, dispatched after.** The row is written inside the
approval's transaction, so there can never be a notified trainer with no allocation or an
allocation nobody was told about. Delivery is a `BackgroundTask` on its own session. There is no
external transport configured, so dispatch marks rows `SENT` for the in-application inbox and is
the single place a real gateway plugs in; failures set `FAILED` and stay visible rather than
being swallowed.

**`GET /evaluations` caps `recorded` at 200 and never caps `awaiting`.** The backlog is the
number that matters; a truncated backlog is a hidden one.

### Conflicts recorded

| # | Item | Resolution |
|---|---|---|
| C13 | Frontend `Allocation.remarks` is `string`; the column is nullable | Coerced to `""` on read. The database keeps "no remark given" distinct from an empty one. |
| C14 | BR-02 and BR-07 are cited in §6.7 but defined only in the SRS | Read from `trainer-prediction-system-SRS.pdf` §2.6: BR-02 "only a Training Administrator may approve"; BR-07 "every allocation decision, approved **or declined**, shall be written to the audit log". Both implemented to that wording — the decline path audits, which a narrower reading would have missed. |
| C15 | §6.7 does not state the programme status after a decline or withdrawal | Returns to `PREDICTED`. Recorded here because it is a decision, not a reading. |
| A7 | `POST /allocations/{id}/accept` · `/decline` | Aliased onto §6.3's `/trainers/me/assignments/{id}/…`. Identity still comes from the token, so the alias adds a path, not a vulnerability. |
| B4 | `GET /notifications?recipientId=` | **Refused.** Every route on the notifications router scopes to the caller. The parameter is accepted by HTTP and ignored; the frontend call site is corrected in Phase 3. |

### Verified over HTTP against the live database

```
FR-08 approve            201  TPS/ALL/2026/0157, PENDING_TRAINER, programme → AWAITING_RESPONSE
  frozen ledger          5 rows, contributions sum 89.81 = frozen score 89.81
  approver               SSP Grace Nabirye, with rank, on the receipt
second approval          409  "already has an allocation (TPS/ALL/2026/0157, PENDING_TRAINER)"
mismatched trainerId     409  "not the trainer shown on screen"
approve as Officer       403  (BR-02)
trainer's assignments    200  pending=1, carrying the rationale that selected them
another trainer accepts  403  (object-level check)
decline, reason "no"     422
decline with a reason    200  DECLINED, declinedAt set, programme → PREDICTED
administrator notified   "IP Sarah Mugisha has declined … Reason: … The next-ranked
                          candidate is ASP Betty Nabirye (rank 5)."
promote-next             201  reusedExistingRun=true, runId unchanged, 1 run still on record
promote-next twice       409
accept                   200  CONFIRMED, programme → ALLOCATED, trainer → ASSIGNED
evaluate before conduct  409  "can only be recorded once the training has been marked conducted"
mark-conducted           200  CONDUCTED
comments < 20 chars      422
record evaluation        201  TPS/EVL/2026/0047, "Recorded. This score now informs future
                              rankings for ASP Betty Nabirye."
evaluate twice           409
receipt after all of it  frozenScore unchanged, evaluationId linked
```

**When reality moves after the ranking** — the four paths that only fire under change:

```
A  candidate marked UNAVAILABLE after the run
   approve → 409 "…can no longer be assigned to this course: Marked unavailable for
                  assignment. (BR-03). This changed after the ranking was generated."
   availability restored → 201
B  promote-next with rank 2 unavailable and rank 3 in court
   → 201, passed over 2, offered to rank 4
     · SP Agnes Nabirye (rank 2): Marked unavailable for assignment.
     · SP Bosco Lubega (rank 3): Unavailable: Giving evidence at the High Court · 20-30 Dec 2026.
   both audited CANDIDATE_SKIPPED
C  approve from a superseded run → 409
D  requirements changed since the run → 409
```

### Quality gates

`104 passed` (77 unit, 12 schema, 15 integration) · `ruff check app/ tests/` clean ·
`mypy app/` clean, 74 source files.

### Defect found in the test harness, not the code

Two integration tests posted programmes titled `"Skip"` and `"Loop"`. `ProgrammeCreate.title` has
`min_length=5`, so both 422'd. The validation was right; the test was wrong.

Two library-level frictions worth recording:

- `Field(multiple_of=Decimal("0.1"))` does not type-check under mypy strict; `decimal_places=1`
  expresses "one decimal place" better anyway.
- `Result.rowcount` is not on the typed `Result` protocol. `mark_all_read` counts before the
  `UPDATE` instead — same transaction, so the count is exact, and it drops a driver dependency.
- Integration tests need `app.db.session.engine` disposed between tests. pytest-asyncio gives
  each test a fresh event loop; asyncpg connections are bound to the loop that opened them, and a
  pooled connection crossing loops surfaces as `got Future attached to a different loop` deep
  inside asyncpg, nowhere near the actual test. An autouse fixture in
  `tests/integration/conftest.py` disposes it.

## P2.9 Stage 7 — administration, audit, dashboard, reports

FR-11, FR-12, FR-13, §6.9–§6.14, plus the `v_trainer_scoring_facts` fix carried over from
Phase 1.

| Component | State |
|---|---|
| `app/schemas/` | `admin.py` (users, roles, audit), `dashboard.py` (dashboard, reports, health) |
| `app/services/` | `user_service.py`, `audit_query_service.py`, `dashboard_service.py`, `report_service.py` |
| `app/api/v1/` | `users.py` (+ `roles_router`), `audit.py`, `dashboard.py`, `reports.py`, `system.py` (+ `system_router`) |
| Migration | `0004_fix_scoring_facts_view.py` |
| Tests | `tests/integration/test_admin_flow.py` — 24 tests |

### Migration 0004 — the view was quietly wrong

`v_trainer_scoring_facts.evaluations_by_discipline_group` reported **1** for every group,
whatever the real figure. The cause was a window function evaluated in the wrong scope: the
inner `LATERAL` was correlated to a *single* evaluation (`e2.evaluation_id = e.evaluation_id`),
so `count(*) OVER (PARTITION BY discipline_group)` counted the rows visible in that one-row
scope — always one. `jsonb_object_agg` then aggregated a column of 1s.

Valid SQL. No error. Plausible shape. Invisible unless you happen to check a trainer you already
know has six evaluations in one group.

```
before   trainer 1 | evaluation_count 6 | {"Investigations": 1}
after    trainer 1 | evaluation_count 6 | {"Investigations": 6}   mean {"Investigations": 4.58}
         trainer 10| evaluation_count 4 | {"Investigations": 3, "Counter-Terrorism": 1}
```

Replaced with four set-based CTEs — group once with `GROUP BY`, then build the JSONB from the
grouped rows. Verified across all 812 trainers: **0 rows where the per-group counts fail to sum
to the total**. Down/up round trip restores the original definition verbatim, bug included; a
downgrade that "fixes" something is a second forward migration in disguise.

The prediction engine never depended on this view — `TrainerRepository.FACTS_SQL` computes its
own per-group figures — but the dashboard and reports do.

### Decisions taken in this stage

**The temporary password never exists outside the response body.** Generated with `secrets`
(not `random` — the seed is deliberately reproducible, a credential must be the opposite),
hashed immediately, and deliberately *not passed to the audit call at all*. The scrubber would
redact a field named `temporary_password`, but the safest redaction is the value never reaching
the call. Asserted by a test that greps the stored row and the audit entry for the plaintext.

**The password alphabet omits `O`, `0`, `I`, `l`, `1`.** An administrator reads these aloud or
writes them on paper. Ambiguous glyphs produce support calls, not security.

**A role change revokes the user's refresh families.** The role travels in the access token, so
a change would otherwise take effect whenever the current token expired. Revoking bounds that to
the access token's lifetime, and the response says so in a sentence via `X-TPS-Notice`.

**The last active System Administrator cannot be deactivated *or suspended*.** §6.10 mentions
only deactivation; suspension has the identical effect and was covered too. Self-deactivation is
also refused — removing your own access is never the intended action.

**Offset paging on `/audit` stops at 10,000 rows.** `OFFSET 200000` makes PostgreSQL walk and
discard 200,000 rows per request, on a table that only grows. Keyset is the documented path;
offset exists because the frontend's table uses it today.

**Reports include trainers with zero allocations.** The empty rows are the finding. A utilisation
report listing only busy people cannot answer the question it exists for — who is never used.

**Both CSV exports stream.** `StreamingResponse` over batched queries, never materialised. Both
are audited as `REPORT_EXPORTED`, and the audit export is audited *before* the stream begins: an
export that failed halfway still means someone read the log.

### Defects found and fixed during verification

| # | Defect | Fix |
|---|---|---|
| 1 | `POST /users` for a TRAINER → **500**. `trainers` declares `directorate_id`, `contact_number` and `searchable_name` `NOT NULL`; the service supplied none of them. | Added the fields to the input schema and a `_assert_trainer_fields` guard that names **every** missing field at once, not just the first. `searchable_name` is set from `full_name` per the model's documented denormalisation. |
| 2 | `GET /audit` → **422** on every request. The `INET` column returns an `ipaddress.IPv4Address`, not a `str`; the DTO typed it as `str`. | A `field_validator(mode="before")` stringifies it. Handles IPv6 too. |
| 3 | `GET /audit?page=2000` → **500**. `PageParams`' deep-offset guard raises inside a `model_validator`, which runs during *dependency construction* — outside `RequestValidationError`'s reach — so it escaped to the catch-all 500 handler. | Registered a handler for bare `pydantic.ValidationError`. The API's own deliberate rule must not be reported as the API breaking. This affected **every** endpoint using `PageParams`, not only audit. |
| 4 | `/system/health/*` → **404**. The system router is mounted at the root (so a container healthcheck need not know the API version); the new §6.14 endpoints landed there too. | Split `system_router` with prefix `/system`, mounted under `/api/v1`. Liveness, readiness and version stay unversioned. |
| 5 | `ReportResponse.filters` went out as `date_from` — snake_case on the wire, breaking B2 in the one place a client reads back its own input. Pydantic's alias generator renames *fields*, not dictionary keys. | Camelised explicitly in `_respond`. Caught by a test, not by review. |

Two of those five (2 and 5) were caught only by driving real requests against real data, and one
(1) only because PostgreSQL refused the insert. The database was right every time.

### Verified over HTTP against the live database

```
FR-12  create as Administrator      403   (System Administrator only)
       create Training Officer      201   14-char temporary password, mustChangePassword=true
       audit entry after creation   {"role": ..., "username": ..., "trainer_profile_created": false}
                                          — no credential in any form
       duplicate username           409
       TRAINER without a posting    422   names all five missing fields
       TRAINER with one            201   trainerId set; profile created in the same transaction
       deactivate own account       409
       suspend the last admin       409   "Create or reactivate another one first"
       deactivation                 403 on the next request with a token issued seconds earlier
                                    0 live refresh sessions remaining
FR-13  audit as Administrator       403
       offset page                  1,127 entries, newest first
       keyset page 1 → page 2       0 overlapping ids
       offset past 10,000 rows      422   "use the cursor-based endpoint"
       POST/PATCH/DELETE /audit     405   the route does not exist
       one allocation's history     3 entries, chronological, approve → accept → conducted
§6.13  dashboard per role           TA: predictionQueue, utilisation, performanceTrend, recentActivity
                                    TO: myRequestsByStatus, requestsNeedingRequirements
                                    TR: pendingInvitations, upcoming, profileCompleteness,
                                        myMeanScore, myScoreTrend
                                    SA: usersByRole, failedSignins24h, lockedAccounts,
                                        activeUsers, predictionRuntimes, auditVolume
       Trainer asking ?role=SA      role=TRAINER — the parameter is ignored, not honoured
FR-11  utilisation                  815 rows; busiest 10, and 766 with none
       allocation history           EVALUATED=54 PENDING_TRAINER=36 DECLINED=10 CONFIRMED=3 CONDUCTED=3
       performance trends           6 quarters, 2026 Q3 mean 3.6 over 11 evaluations
       reports as Trainer/Officer   403
       CSV export                   200 text/csv, 816 lines, Content-Disposition set, audited
§6.14  prediction performance       74 runs/30 days, mean 347ms, slowest 2,316ms,
                                    threshold 10,000ms, breaches 0
       security                     failedSignins24h=8 locked=0 unauthorised24h=2
                                    activeSessions=192 deactivated=9 failedNotifications=0
```

### Conflicts recorded

| # | Item | Resolution |
|---|---|---|
| A4/A5 | `/reports/allocations`, `/reports/performance` | Aliased onto `/allocation-history` and `/performance-trends`. |
| A8 | `GET /dashboard?role=` | Aliased onto `/dashboard/summary`. The role is derived from the token in both. |
| B3 | `GET /dashboard?role=&userId=` | **Refused.** Both parameters are accepted by HTTP, marked deprecated in the schema, and discarded. A Trainer requesting the Administrator dashboard receives the Trainer dashboard. |
| C2 | `GET /users` → bare `User[]` | Returns the paginated envelope. Frontend adapts in Phase 3. |
| C4 | `GET /audit` offset vs keyset | Both. Keyset via `?after=`, offset capped at 10,000. |
| C16 | `mark-conducted` audits as `USER_MODIFIED` | No dedicated action exists, and `domain.ts:AuditAction` is a closed union — adding a member would break the frontend contract before Phase 3. The `detail` sentence carries the meaning. Revisit when the union is updated. |

## P2.10 Stage 8 — rate limiting, the authorisation matrix, and documentation

§7.1, §7.5, §14.2, §14.3.

| Component | State |
|---|---|
| `app/core/rate_limit.py` | slowapi limiter, forwarded-address keying, login + simulate limits wired |
| `tests/integration/test_authorization.py` | the matrix — every route × every wrong role, plus object-level ownership |
| `tests/integration/test_rate_limiting.py` | the limiter fires, in the standard error shape, keyed behind a proxy |
| `docs/ALGORITHMS.md` | the 12-section justification, with the real EXPLAIN and NFR-01 measurements |
| `ARCHITECTURE.md`, `API-GUIDE.md` | the layering rule, request lifecycle, RBAC matrix, one full worked scenario |
| `README.md` | brought up to Phase 2: run instructions, troubleshooting, testing, guarantees, limits |
| `docs/adr/0012`–`0017` | §6-canonical, in-process rate limiting, Decimal, async session, JWT rotation, container-to-host |
| `docs/openapi.json` + `scripts/export_openapi.py` | exported and committed, with a `--check` mode for CI |

### The rate limiter was constructed but never applied

`main.py` built a `Limiter` and attached it to `app.state`, but no route carried
`@limiter.limit(...)`, so nothing was ever throttled. Moved the limiter to
`app/core/rate_limit.py` (module-level, so route decorators reference it at import time)
and decorated `POST /auth/login` (10/min) and `POST /predictions/simulate` (30/min).

Keyed on the **forwarded** address, not the socket. Behind a reverse proxy the socket
address is the proxy's, so socket-keying would put a whole district behind one counter
and the first burst would lock them all out. The header is client-controllable, which is
acceptable for a limiter (worst case: an attacker mints fresh buckets, no worse than no
limit) and would not be for authorisation.

Verified: 10 sign-in attempts answered 401, the 11th and 12th 429, in the RFC 9457 shape
with `retryAfterSeconds`. Recorded as ADR-0013 with its stated limitation — in-process
state means the effective limit multiplies by the replica count.

### The authorisation matrix

`test_authorization.py` — §7.1's "single highest-value artefact". Three assertions:

1. **Authentication.** Every route, no token → 401.
2. **Role.** Every route × every wrong role → 403. Not 404 (which still discloses the
   resource) and not 422 (which means the request reached validation). Read and write
   routes both; write routes carry empty bodies, so a 422 would prove the role gate sits
   *downstream* of parsing.
3. **Object-level ownership.** A Trainer cannot read another trainer's profile,
   evaluations, allocation, or credentials, and cannot accept or decline another's
   assignment. `?recipientId=` on notifications is ignored, not honoured. Marking another
   user's notification read is 404, not 403 — the difference is itself information.

**The matrix cross-checks itself against the live OpenAPI schema.** A route added without
a line in the matrix fails `test_the_matrix_covers_every_documented_route`, which is what
stops the checklist from rotting as the API grows.

### Defect found: the rate limiter broke the whole suite

Turning the limiter on surfaced immediately: every test signs in up to four times for
role headers, and the suite makes several hundred sign-ins from 127.0.0.1 in under a
minute — past the 10/min limit. Unrelated tests began failing with 429s that looked like
authorisation bugs.

Fixed with an autouse fixture that disables the limiter for the suite and a dedicated
`test_rate_limiting.py` that re-enables it deliberately. Disabling in the fixture rather
than lowering the limit in config keeps the production value exactly as shipped.

### Harness defect, not a code defect

The matrix first used `request.getfixturevalue(name)` to pick a role's headers by string.
That raises `Runner.run() cannot be called from a running event loop` — the fixtures are
async, and resolving one lazily inside a running test tries to start a second loop. Fixed
by requesting all four role fixtures as parameters and mapping them in a plain dict.

### `docs/openapi.json` exported and committed

73 paths, 85 operations, 89 schemas. `scripts/export_openapi.py` renders it with sorted
keys so registration-order churn does not appear as a diff, and has a `--check` mode that
exits non-zero when the committed file is stale — a CI step that catches an API change
shipped without its schema.

### Documentation

`docs/ALGORITHMS.md` is written for a supervising officer or external examiner: the
honest rejection table for ML/TOPSIS/AHP/ELECTRE, the shrinkage derivation with a worked
n = 0…12 table, the confidence decay and its "data completeness, not likelihood of
success" caveat, the real facts-query rewrite (995 ms → 62–83 ms) and NFR-01 measurements
(mean 347 ms, 0 breaches over 74 runs), the float-drift argument for `Decimal`, and a §12
that states where the model is weak — including the honest observation that PERFORMANCE
currently discriminates weakly against the seeded prior.

Six new ADRs (0012–0017) cover every decision §14.3 names. `ARCHITECTURE.md` states the
downward-dependency rule as a one-line grep, the request lifecycle, the transaction
boundary with its single documented exception, and how to add a scoring criterion with no
migration. `API-GUIDE.md` carries the full FR-04 → FR-10 worked scenario with real
payloads.

### Two authorisation findings the matrix surfaced

The matrix did its job on first run — two real gaps and one test bug.

**1. `/trainers/me/*` write routes returned 422, not 403, for a non-trainer.** These
routes had no `require_roles` gate; they relied on `current_trainer_id(user)` inside the
handler, which raises 403 when the account has no linked trainer profile. But that runs
*after* body parsing, so a Training Administrator POSTing to `/trainers/me/qualifications`
got a 422 from body validation before the 403 ever fired. The role check sat downstream of
parsing — refused today, one refactor from not being, and inconsistent with
`/trainers/me/assignments`, which was correctly gated.

Fixed by adding `dependencies=[Depends(require_roles(TR))]` to all 13 `/me` routes, so the
refusal is a clean 403 *before* the body is read. `current_trainer_id` stays as the
layer-2 "has a linked profile" check. This is the same 422-before-403 class as defect #3
in Stage 7 — the guard was outside the request-validation path.

**2. My matrix under-stated `GET /programmes/{id}/prediction`.** I asserted `(TA, TO)`;
the code allows `(TA, TO, SA)`, consistent with `GET /predictions/runs/*`, `GET /allocations`,
and `GET /allocations/{id}` — **SA has read-only oversight across the decision surface**,
never write. §6.4 lists only "TA, TO" for this one route, but the code is internally
consistent in giving the oversight role read access, and that is the more defensible
position than a lone exception. Matrix aligned to the code; the widening is read-only and
documented here.

**3. Test bug, not a code bug.** `test_the_matrix_covers_every_documented_route` fetched
`/openapi.json` against a client whose `base_url` is `/api/v1`, resolving to
`/api/v1/openapi.json` (404). Fixed to fetch the app root explicitly.

The `/me/*` gate changed the documented surface, so `docs/openapi.json` was re-exported.

### The coverage test caught 13 genuinely-untested routes

Once the OpenAPI fetch was fixed, `test_the_matrix_covers_every_documented_route` did
exactly what it is for: it failed, naming 13 documented routes with **no line in the
authorisation matrix** — every DELETE on `/trainers/me/*`, `/audit/export`,
`/audit/entity/*`, `/evaluations/{id}`, the single-candidate prediction detail,
`/reports/{type}/export`, `PATCH /programmes/{id}`, `/auth/logout`,
`/auth/change-password`, and both notification mutations.

None had a *bug* — each carries the right gate — but none was *tested*, which is the
precise gap this test exists to close. All 13 are now in the matrix with their roles, so
each is exercised against every wrong role.

The path-matching was also rewritten to compare **segment patterns** — a documented
`{param}` is a wildcard any concrete matrix segment satisfies — rather than normalising
ids, entity types (`ALLOCATION`), and enum path values (`utilisation`) to a shared
placeholder. Each of those would otherwise have needed its own special case, and one
would eventually have been forgotten.

## P2.11 Containerisation — built, and verified end to end

The image that would not build in the earlier session now builds. The blocker was
IPv6-without-a-route (`curl -6` hangs, `curl -4` returns immediately); the fix —
`/etc/docker/daemon.json` with `{"dns": ["8.8.8.8","1.1.1.1"]}` — was applied and held.

```
docker build           328 MB, non-root uid 1001, no build tooling in the runtime layer
```

### Container-to-host database, proven

Run under the documented Compose model (`host.docker.internal` + `host-gateway`), the API
starts and **correctly self-diagnoses** that the host PostgreSQL is not yet on the Docker
bridge:

```json
{"status": "not_ready",
 "dependencies": [{"name": "postgresql", "healthy": false,
   "detail": "Cannot reach PostgreSQL at host.docker.internal:5432 … needs a host-gateway
              entry in Compose and PostgreSQL listening on the Docker bridge …
              ConnectionRefusedError."}]}
```

That is the readiness probe working exactly as designed — a diagnosis, not a stack trace.

The three host-side settings (ADR-0017, README troubleshooting) require the operator's
`sudo`, so completing the bridge path is the user's step. To prove the **image and
application** are correct independently of that, the container was run with host
networking against the host PostgreSQL on `localhost`:

```
GET /health/ready        {"status":"ready","healthy":true,"detail":"Connected to
                          localhost:5432/tps_db.","latencyMs":7.42}
POST /auth/login         token issued
GET  /dashboard/summary  role=TRAINING_ADMINISTRATOR, awaitingApproval=52
GET  /trainers?pageSize=1 total 817
GET  /version            1.0.0
whoami inside            uid=1001(tps) — non-root confirmed
```

The whole stack — auth, RBAC, pagination, the database round trip — runs inside the
container against the real host database. Once the operator enables the Docker bridge
with the three documented `sudo` commands, the same works through
`host.docker.internal` under Compose with no image change.

### To enable the bridge (operator, one time)

```bash
# 1. PostgreSQL listens on the Docker bridge as well as localhost
sudo sed -i "s/^#*listen_addresses.*/listen_addresses = 'localhost,172.17.0.1'/" \
  /etc/postgresql/18/main/postgresql.conf

# 2. Permit the Docker subnet, scram-sha-256
echo "host  tps_db  tps_app  172.16.0.0/12  scram-sha-256" \
  | sudo tee -a /etc/postgresql/18/main/pg_hba.conf

# 3. Restart
sudo systemctl restart postgresql

# then, from backend/
API_PORT=8000 docker compose up -d
docker compose exec backend alembic upgrade head   # migrations are an explicit step (B12)
```
