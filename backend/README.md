# TPS Backend

**Trainer Prediction System** · Uganda Police Force · Directorate of Human Resource Development

A decision support system that ranks trainers against training programme requirements
and records the resulting allocation as an auditable decision.

**It does not decide.** BR-06 makes that structural: no allocation is final without an
explicit Training Administrator approval, and there is no auto-approve path anywhere in
the API. What the system provides is a ranking a person can check by hand, and a record
of what they saw when they approved it.

PostgreSQL 18 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · asyncpg · Pydantic v2 · uv

| | |
|---|---|
| **Phase 1** — persistence | 26 tables, 1 view, 4 migrations, deterministic seed |
| **Phase 2** — API | 73 documented endpoints, 5-criterion scoring engine, RBAC in two layers |
| Where to read next | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`API-GUIDE.md`](API-GUIDE.md) · [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) |

---

## Get running in under ten minutes

### 1. PostgreSQL (once per machine)

PostgreSQL must already be installed and running. Create the role, database, and
extensions as a superuser:

```bash
sudo -u postgres psql -c "CREATE ROLE tps_app WITH LOGIN PASSWORD 'tps_dev_2026';"
sudo -u postgres psql -c "CREATE DATABASE tps_db OWNER tps_app ENCODING 'UTF8' TEMPLATE template0;"
sudo -u postgres psql -d tps_db \
  -c "ALTER SCHEMA public OWNER TO tps_app;" \
  -c "GRANT ALL ON SCHEMA public TO tps_app;" \
  -c "CREATE EXTENSION IF NOT EXISTS citext;" \
  -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" \
  -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"
```

`ALTER SCHEMA public OWNER` is not optional. PostgreSQL 15 and later no longer grant
`CREATE` on `public` to `PUBLIC`, and without it Alembic fails with *permission denied
for schema public* on the first migration.

Choose a password without `@ : / ? # [ ] %` — those are URI-reserved and must be
percent-encoded in every connection string.

Verify — four rows, including `btree_gist`, `citext`, and `pg_trgm`:

```bash
PGPASSWORD='tps_dev_2026' psql -h localhost -U tps_app -d tps_db -c "\dx"
```

### 2. The backend

```bash
cd backend
uv sync
cp .env.example .env        # then set POSTGRES_PASSWORD and POSTGRES_HOST=localhost
```

`JWT_SECRET_KEY` must be set to something real. The application **refuses to start** in
production with a weak or default secret — a signing key that ships in a repository
signs tokens anybody can forge:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Schema and data

```bash
POSTGRES_HOST=localhost uv run alembic upgrade head
POSTGRES_HOST=localhost uv run python -m scripts.seed
POSTGRES_HOST=localhost uv run python -m scripts.verify
```

`POSTGRES_HOST=localhost` is needed because these commands run **on the host**. The
committed default in `.env.example` is `host.docker.internal`, which is what the
container uses.

Expect: `alembic upgrade head` creates 26 tables and one view; the seed writes ~37,800
rows in under 20 seconds; verify reports **30 checks passed**.

### 4. Run the API

```bash
POSTGRES_HOST=localhost uv run uvicorn app.main:app --reload --port 8000
```

Then:

- **http://localhost:8000/docs** — Swagger UI, every endpoint with its rules explained
- **http://localhost:8000/health/ready** — readiness, with a per-dependency breakdown
- **http://localhost:8000/api/v1/auth/login** — sign in and start exercising it

```bash
curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin.training", "password": "Tps@2026#Demo"}'
```

### 5. Or in Docker

```bash
docker compose up --build
```

The container reaches the **host's** PostgreSQL through `host.docker.internal`. Three
host-side settings must be right; see [Troubleshooting](#troubleshooting) — each has a
distinctive error message.

---

## Demo accounts

Password for all four: **`Tps@2026#Demo`**

| Username | Name | Rank | Role |
|---|---|---|---|
| `admin.training` | Grace Nabirye | SSP | Training Administrator |
| `officer.training` | Joseph Okello | ASP | Training Officer |
| `trainer` | Sarah Mugisha | IP | Trainer |
| `sysadmin` | Denis Byaruhanga | SP | System Administrator |

Every other seeded account has **no usable password** and cannot be signed into. They
are data, not credentials. Hashing 850 accounts individually with the configured
Argon2id parameters costs 220 seconds (measured), and giving them all a *known*
password would be worse than giving them none.

> The frontend hard-codes `Demo@2026` at `frontend/src/hooks/useAuth.ts:16`. Phase 3
> must change that one line to `Tps@2026#Demo`, or the sign-in hint will be wrong the
> moment `VITE_USE_MOCKS=false`.

---

## Commands

| Command | What it does |
|---|---|
| `uv run alembic upgrade head` | Apply all migrations |
| `uv run alembic downgrade base` | Unwind cleanly to nothing |
| `uv run alembic revision --autogenerate -m "..."` | Draft a migration — **always review it** |
| `uv run python -m scripts.seed` | Generate and load the demo dataset (idempotent) |
| `uv run python -m scripts.verify` | Assert 30 schema and data invariants |
| `uv run python -m scripts.reset` | Wipe transactional data, keep reference data and demo accounts |
| `uv run python -m scripts.reset --all` | Wipe everything, back to a bare migrated schema |
| `uv run python -m scripts.reset --dry-run` | Report what would be deleted |
| `uv run python -m scripts.gen_data_dictionary` | Regenerate `docs/DATA-DICTIONARY.md` from the live database |
| `uv run ruff check . && uv run ruff format .` | Lint and format |
| `uv run mypy app/ scripts/ data/` | Type-check (strict) |
| `uv run uvicorn app.main:app --reload` | Run the API with auto-reload |
| `POSTGRES_HOST=localhost uv run pytest` | Run the whole suite (needs a seeded database) |
| `uv run pytest tests/unit` | Unit tests only — no database needed |
| `uv run pytest tests/integration/test_authorization.py` | The authorisation matrix alone |
| `uv run python -m scripts.export_openapi` | Regenerate `docs/openapi.json` |

Both reset modes require typed confirmation (`RESET` or `WIPE EVERYTHING`). This is
the only destructive command here, and it exists to be run against a database someone
cares about.

---

## Layout

```
backend/
├── app/
│   ├── api/           routers (v1/) and shared dependencies — the only layer knowing HTTP
│   ├── core/          config, security, errors, pagination, clock, rate limiting
│   ├── db/            declarative base, naming convention, session, column types
│   ├── middleware/    correlation id, request logging, audit context
│   ├── models/        26 tables across 8 domain modules + enums
│   ├── repositories/  projections and the engine facts query
│   ├── schemas/       Pydantic DTOs — camelCase on the wire, snake_case in Python
│   └── services/      business logic. Imports no `fastapi`, by rule (B7)
│       └── prediction/  the scoring engine: gates, criteria, confidence, narrative
├── migrations/
│   └── versions/
│       ├── 0001_initial_schema.py         autogenerated, hand-reviewed
│       ├── 0002_triggers_and_functions.py hand-written: what Alembic cannot see
│       ├── 0003_scoring_facts_view.py     hand-written: v_trainer_scoring_facts
│       └── 0004_fix_scoring_facts_view.py the per-group aggregate bug
├── data/seed_source/  deterministic generator + a seed-only port of the scoring engine
├── scripts/           seed, reset, verify, data-dictionary, openapi export
├── tests/
│   ├── unit/          the scoring engine — 77 tests, no I/O
│   └── integration/   real app, real database, nothing mocked
└── docs/
    ├── ALGORITHMS.md       why this method, and where it is weak
    ├── DATA-DICTIONARY.md  generated — do not edit
    ├── ERD.md              Mermaid diagram
    ├── openapi.json        exported, so API changes appear as diffs
    └── adr/                17 architecture decision records
```

---

## What the schema guarantees

These are enforced **by the database**, not by convention, and `scripts/verify.py`
proves each one by attempting to violate it:

| Guarantee | Mechanism |
|---|---|
| Audit entries cannot be edited or deleted (FR-13) | `BEFORE UPDATE OR DELETE` trigger raising an exception |
| Exactly one scoring policy is active | Partial unique index `WHERE is_active` |
| A policy's weights sum to 100 | Deferred constraint trigger firing at `COMMIT` |
| A trainer cannot be absent twice at once | `EXCLUDE USING gist` on `(trainer_id, daterange)` |
| No two trainers rank first in one run | `UNIQUE (run_id, rank_position)` |
| A declined allocation carries a reason (FR-09) | `CHECK (status <> 'DECLINED' OR decline_reason IS NOT NULL)` |
| One prediction becomes at most one allocation (D7) | `UNIQUE` on `allocations.prediction_id` |
| Registry numbers never collide | PostgreSQL sequences, never `MAX(id)+1` |

Read `docs/adr/0005` and `docs/adr/0011` for what these guarantees **do not** cover —
both state their limits explicitly rather than overclaiming.

---

## The seed tells a story

The dataset is not uniform noise. It replays a plausible history chronologically —
each prediction run sees only the evaluations that existed on its own date — and it
asserts eight narrative fixtures before writing anything. If a fixture fails to
materialise, the seed **fails loudly** rather than producing a demo with an empty
chart.

1. The featured cybercrime course has ranks 1 and 2 **0.5 points apart**, so the Weight
   Studio visibly changes the outcome.
2. A top-five candidate has **zero evaluations** and therefore LOW confidence — twenty
   years of service, never formally evaluated. The cold-start caveat, visible at once.
3. A declined allocation, **corroborated** by a matching court-attendance absence
   window rather than by a bare string.
4. Two courses `CONDUCTED` but not `EVALUATED`, so Record Evaluation is live.
5. A real Exclusion Ledger — 52 unavailable, 54 lacking the specialisation.
6. One trainer allocated **four times in six months** while equally qualified peers
   have none. This is the over-reliance pattern the SRS problem statement describes.
7. Evaluations spanning **six quarters**, so performance trends have a real series.
8. Failed sign-ins and one account lockout, so System Health is not empty.

Determinism comes from a single `random.Random(20260722)` threaded through every
generator. Reordering any loop in `data/seed_source/generator.py` changes the entire
dataset.

---

## Known deviations

Recorded in full in `PROGRESS.md` §3 and the ADRs; the three that affect other people:

1. **Real UPF reference data** is seeded instead of the frontend's simplified lists
   (ADR-0009). No TypeScript contract breaks — all these fields are typed `string` —
   but `frontend/src/lib/constants.ts` needs updating in Phase 3.
2. **The demo password differs** from the frontend's hard-coded constant, as above.
3. **§7.1's stated seed volumes are wrong** for predictions, allocations, and
   evaluations; the measured mock figures were used instead (ADR-0010).

---

## Troubleshooting

The three failures a fresh machine actually hits, with the exact symptom — because the
symptom is what you search for.

### `could not translate host name "host.docker.internal"`

The container cannot resolve the host. On Linux this alias does not exist by default;
`docker-compose.yml` supplies it:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

If you are running the API **on the host** rather than in Docker, set
`POSTGRES_HOST=localhost` instead. That single variable is the only difference.

### `connection refused` from inside the container

PostgreSQL is listening on `localhost` only. Add the Docker bridge address:

```bash
sudo -u postgres psql -c "SHOW config_file;"      # find postgresql.conf
# listen_addresses = 'localhost,172.17.0.1'
sudo systemctl restart postgresql
```

Confirm the bridge address — it is not always `172.17.0.1`:

```bash
ip addr show docker0 | grep 'inet '
```

### `no pg_hba.conf entry for host "172.17.0.x"`

PostgreSQL is listening but refusing the Docker subnet. Append to `pg_hba.conf`:

```
host    tps_db    tps_app    172.16.0.0/12    scram-sha-256
```

Then `sudo systemctl reload postgresql`.

> **Append with a here-doc or an editor, not by pasting a shell command into the file.**
> A stray `sudo` line in `pg_hba.conf` produces `FATAL: could not load pg_hba.conf` and
> the server will not start — recoverable, but not at a convenient moment.

### `permission denied for schema public`

PostgreSQL 15+ no longer grants `CREATE` on `public` to `PUBLIC`. Run the
`ALTER SCHEMA public OWNER TO tps_app` from step 1.

### `password authentication failed` with a correct password

The password contains a URI-reserved character (`@ : / ? # [ ] %`) and is not
percent-encoded in the connection string. `bolt@9` must be written `bolt%409`. Simpler
to choose an alphanumeric password.

### The image build fails at `uv sync` with a DNS or timeout error

Usually IPv6: the name resolves to an AAAA record with no working IPv6 route, so the
connection hangs until it times out. Check with `curl -6 https://pypi.org` — if that
hangs while `curl -4` returns immediately, force IPv4 DNS in `/etc/docker/daemon.json`:

```json
{"dns": ["8.8.8.8", "1.1.1.1"]}
```

Then `sudo systemctl restart docker`.

### The port is already in use

```bash
API_PORT=8001 docker compose up
```

`docker-compose.yml` maps `${API_PORT:-8000}:8000` precisely so this does not require
editing a committed file.

---

## Testing

```bash
POSTGRES_HOST=localhost uv run pytest              # everything
uv run pytest tests/unit                           # engine only, no database
```

Integration tests run against the **real** database over the **real** ASGI app. Nothing
is mocked, deliberately: the properties worth testing here — the transaction boundary,
the `CHECK` constraints, the RBAC dependencies, the frozen snapshot — are properties of
the whole assembly, and every one of them would survive a mock.

| File | What it proves |
|---|---|
| `tests/unit/test_prediction_engine.py` | The scoring engine, 77 tests, every branch |
| `tests/test_schema_guarantees.py` | The database refuses what it promises to refuse |
| `tests/integration/test_allocation_flow.py` | The whole spine: create → predict → approve → decline → promote → conduct → evaluate, and that the evaluation shifts the next prediction |
| `tests/integration/test_admin_flow.py` | Users, audit, dashboard, reports |
| `tests/integration/test_authorization.py` | **Every route × every wrong role → 403**, plus object-level ownership |
| `tests/integration/test_rate_limiting.py` | The limiter fires, in the standard error shape |

`test_authorization.py` cross-checks its own matrix against the live OpenAPI schema, so
a route added without a line in the matrix **fails the test** rather than going quietly
untested. That is what stops a hand-maintained security checklist from rotting.

---

## What the API guarantees

Beyond the schema guarantees above, these are properties of the application layer and
each has a test:

| Guarantee | Where |
|---|---|
| An approval re-checks the hard gates against **live** data, not the ranking's snapshot | `allocation_service._recheck_gates` |
| The Decision Receipt is frozen at approval and never recomputed | `allocation_service._create_allocation` — the only writer of those five columns |
| A decline reuses the existing run; no re-prediction | `promote_next`, `reusedExistingRun: true` |
| Deactivation takes effect on the **next request**, not at token expiry | `deps.get_current_user` re-reads account status |
| A temporary password is never stored, logged, or audited in plaintext | `user_service.create` |
| Every mutation's audit entry shares the mutation's transaction | `AuditService.record` — flushes, never commits |
| Scores are `Decimal` end to end; two runs produce identical rankings | ADR-0014 |

---

## Known limitations

Stated here rather than discovered later. Full treatment in
[`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) §12.

1. **Rate limiting is in-process.** Correct with one container; with several, the
   effective limit multiplies by the replica count (ADR-0013).
2. **Notification delivery has no external transport.** Rows are written and marked
   `SENT` for the in-application inbox; there is no SMS gateway or mail relay. The
   `delivery_status` column exists so one can be added without a schema change.
3. **PERFORMANCE currently discriminates weakly**, because the seeded prior sits close
   to most trainers' observed means. Re-examine once real evaluations accumulate.
4. **The frontend has no refresh flow.** With a 15-minute access token that signs the
   user out every 15 minutes. Phase 3 must add it.
