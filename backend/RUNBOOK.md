# Running the whole system locally

What runs where, in how many terminals, and how to tell each part is healthy. Nothing
here changed when the project gained Render/Supabase support — local development still
uses your **host PostgreSQL** and is completely unaffected by the deployment config.

---

## The moving parts

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  YOUR MACHINE                                                              │
  │                                                                            │
  │   PostgreSQL 18            FastAPI backend            React frontend       │
  │   (host service)     ◀──   uvicorn :8001       ◀──   vite dev :5173        │
  │   127.0.0.1:5432           (this repo)                (the other repo)     │
  │        ▲                        ▲                          ▲               │
  │   always running          Terminal 1                  Terminal 2          │
  │   (systemd)                                                                │
  └──────────────────────────────────────────────────────────────────────────┘
```

- **PostgreSQL** is a background system service (systemd) — not a terminal you keep open.
- **Terminal 1** — the backend API.
- **Terminal 2** — the frontend dev server (in its own repository).

Two terminals for day-to-day work. Migrations and the seed are **one-off commands**, not
long-running processes — run them when needed and they exit.

---

## Prerequisites (once per machine)

PostgreSQL must be installed and the role/database/extensions created — this is Phase 1's
setup, in `README.md`. Confirm it is up:

```bash
pg_isready -h localhost -p 5432          # → "accepting connections"
psql "postgresql://tps_app:tps_dev_2026@localhost:5432/tps_db" -c "\dt" | head
```

If the `\dt` shows tables, the schema and seed are already loaded and you can skip the
one-off commands below.

---

## One-off commands (only when needed)

Run from `backend/`. These finish and exit — they are not servers.

```bash
uv sync                                              # install/refresh dependencies

POSTGRES_HOST=localhost uv run alembic upgrade head  # create/upgrade the schema
POSTGRES_HOST=localhost uv run python -m scripts.seed    # load demo data (idempotent, ~20s)
POSTGRES_HOST=localhost uv run python -m scripts.verify  # 30 invariant checks
```

`POSTGRES_HOST=localhost` is needed because the committed `.env` default is
`host.docker.internal` (for the container). On the host you point at `localhost`.

To start over: `POSTGRES_HOST=localhost uv run python -m scripts.reset --all` (asks for
typed confirmation), then re-run migrate + seed.

---

## Terminal 1 — the backend API

```bash
cd backend
POSTGRES_HOST=localhost uv run uvicorn app.main:app --reload --port 8001
```

Port **8001**, because 8000 is taken by another project on this machine. Watch for:

```
database_reachable   host=localhost
Application startup complete.
Uvicorn running on http://127.0.0.1:8001
```

Healthy when:

```bash
curl -s localhost:8001/health/ready        # {"status":"ready", … "Connected to localhost:5432/tps_db."}
```

Interactive API docs while it runs: **http://localhost:8001/docs**

`--reload` restarts the server on any code change. Leave this terminal open while working.

---

## Terminal 2 — the frontend

In the **frontend** repository (separate from this one):

```bash
cd <path-to-frontend-repo>
npm install                                # once
npm run dev                                # Vite dev server on http://localhost:5173
```

Point the frontend at the local API. In the frontend repo's `.env` (or `.env.local`):

```
VITE_API_BASE_URL=http://localhost:8001/api/v1
VITE_USE_MOCKS=false
```

The backend already allows `http://localhost:5173` in CORS by default, so no backend
change is needed for local frontend work.

> To run the frontend against its mock adapter instead of the real API, set
> `VITE_USE_MOCKS=true` — then Terminal 1 is not needed at all.

---

## Sign in

Four demo accounts, all with password **`Tps@2026#Demo`**:

| Username | Role | What they can do |
|---|---|---|
| `admin.training` | Training Administrator | Approve allocations, predict, evaluate |
| `officer.training` | Training Officer | Raise requests, predict — cannot approve |
| `trainer` | Trainer | Own profile, accept/decline own assignments |
| `sysadmin` | System Administrator | Users, audit, system health |

---

## Running the tests

A third terminal, only when you want it. Needs the seeded local database.

```bash
cd backend
POSTGRES_HOST=localhost uv run pytest              # everything (~6 min)
uv run pytest tests/unit                           # engine only, no database (~5s)
uv run pytest tests/integration/test_authorization.py   # the RBAC matrix
```

Quality gates:

```bash
uv run ruff check . && uv run mypy app/
uv run python -m scripts.export_openapi --check    # docs/openapi.json in sync with the code
```

---

## Running against Supabase from your laptop (optional)

You can point the *local* API at the *hosted* database — useful to reproduce a
production issue. It does not change your `.env`; it only affects the one shell:

```bash
export DATABASE_URL='postgresql://postgres.xwvrdgodigxxuzvuvwfn:PASSWORD@aws-0-<region>.pooler.supabase.com:5432/postgres'
uv run uvicorn app.main:app --reload --port 8001
# /health/ready now reports the Supabase pooler host; TLS is enabled automatically.
unset DATABASE_URL   # back to local
```

---

## Running the container locally

The image is what Render builds. To run it against your host database:

```bash
# Bridge mode (the documented Compose model) needs host PostgreSQL on the Docker bridge —
# three sudo settings in README "Troubleshooting". Once done:
API_PORT=8000 docker compose up --build

# Or, with no host config, host networking against localhost:
docker run --rm --network host \
  --env-file .env -e POSTGRES_HOST=localhost \
  --entrypoint uvicorn tps-backend:1.0.0 app.main:app --host 0.0.0.0 --port 8003
curl -s localhost:8003/health/ready
```

---

## Quick reference

| I want to… | Command |
|---|---|
| Start the API | `POSTGRES_HOST=localhost uv run uvicorn app.main:app --reload --port 8001` |
| Check it is healthy | `curl -s localhost:8001/health/ready` |
| Open the API docs | browse to `http://localhost:8001/docs` |
| Load/refresh demo data | `POSTGRES_HOST=localhost uv run python -m scripts.seed` |
| Wipe and start over | `POSTGRES_HOST=localhost uv run python -m scripts.reset --all` |
| Run all tests | `POSTGRES_HOST=localhost uv run pytest` |
| Point local API at Supabase | `export DATABASE_URL='…pooler…'` then start the API |
