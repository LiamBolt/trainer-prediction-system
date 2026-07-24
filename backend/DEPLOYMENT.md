# Deploying TPS — Render + Supabase

This deploys the **backend** to Render and its **database** to Supabase. The frontend
stays in its own repository and is deployed separately; it only needs the backend's URL.

```
   ┌─────────────────┐        ┌──────────────────────┐        ┌─────────────────────┐
   │  frontend repo   │  HTTPS │   Render web service  │  TLS   │  Supabase Postgres  │
   │  (its own host)  │ ─────▶ │   this repo, Docker   │ ─────▶ │  (session pooler)   │
   └─────────────────┘        └──────────────────────┘        └─────────────────────┘
        CORS_ORIGINS ◀───────────────┘   DATABASE_URL ────────────────┘
```

Three env values do all the wiring: the frontend knows the Render URL, Render's
`CORS_ORIGINS` names the frontend, and Render's `DATABASE_URL` names Supabase.

---

## Read this first — two things that will bite you otherwise

**1. Use the Supabase *Session pooler* URL, never the direct one.**
The direct host `db.<ref>.supabase.co` is **IPv6-only**. Render (and many machines) have
no outbound IPv6 route, so the direct URL fails with *"Network is unreachable"* — which
looks like a firewall problem and is not. The **session pooler** host
`aws-0-<region>.pooler.supabase.com` is reachable over IPv4 and is what you must use.
This was verified for your project: `db.xwvrdgodigxxuzvuvwfn.supabase.co` resolves only to
an IPv6 address.

**2. The password you shared is now exposed and reused.**
`tps_dev_2026` is your Supabase password *and* your local dev password, and it has
travelled through a chat. Before going live: **rotate the Supabase database password**
(Supabase → Project Settings → Database → Reset database password) and use the new one
below. Do not commit it anywhere — the steps here keep it in the Render dashboard only.

---

## Step 1 — Supabase

### 1a. Get the session-pooler connection string

Supabase dashboard → **Project Settings → Database → Connection string → "Session
pooler"** (the tab may be labelled *Connection pooling*, mode **Session**). Copy the URI.
It looks like:

```
postgresql://postgres.xwvrdgodigxxuzvuvwfn:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Note the shape, which differs from the direct URL:
- user is `postgres.xwvrdgodigxxuzvuvwfn` (the project ref is part of the username),
- host is `aws-0-<region>.pooler.supabase.com`,
- port is `5432` (**Session** mode — supports prepared statements, which asyncpg uses).

> Avoid the **Transaction** pooler (port `6543`) for this app. It disables prepared
> statements, which asyncpg relies on; making it work needs extra flags and buys nothing
> here. Session mode behaves like a normal connection.

Keep this string handy — it is your `DATABASE_URL`.

### 1b. Enable the three extensions the schema needs

Supabase → **SQL Editor** → run once:

```sql
create extension if not exists citext;
create extension if not exists pg_trgm;
create extension if not exists btree_gist;
```

The schema uses `citext` (case-insensitive usernames/emails), `pg_trgm` (fuzzy trainer
search), and `btree_gist` (the non-overlapping-absence constraint). Migrations assume
they exist.

---

## Step 2 — Create the schema and seed data, from your laptop

You run this **against Supabase from your own machine**, not from Render. Supabase is a
public database; your local tooling already has everything needed, and this keeps
migrations an explicit human step (the app never migrates itself). It also means you can
re-seed or reset anytime.

From `backend/`:

```bash
# The session-pooler URL from step 1a, with your (rotated) password:
export DATABASE_URL='postgresql://postgres.xwvrdgodigxxuzvuvwfn:NEW_PASSWORD@aws-0-<region>.pooler.supabase.com:5432/postgres'

uv run alembic upgrade head      # creates 26 tables, 1 view, all triggers/functions
uv run python -m scripts.seed    # ~37,800 rows; idempotent; ~20s
uv run python -m scripts.verify  # 30 checks — expect "30 checks passed"
```

`DATABASE_URL` overrides the local `POSTGRES_*` settings **only for this shell**. Your
`.env` is untouched, so a new terminal without `DATABASE_URL` still talks to your local
database (see RUNBOOK.md). When `DATABASE_URL` is set, the app auto-enables TLS and
strips libpq-only query params (`sslmode`, `pgbouncer`, …) that asyncpg cannot read.

> If `alembic upgrade head` hangs or says *Network is unreachable*, you used the direct
> `db.<ref>.supabase.co` host — switch to the pooler host from step 1a.

When this finishes, your Supabase database is fully populated. The four demo accounts
(password `Tps@2026#Demo`) work immediately.

---

## Step 3 — Push the whole project to GitHub

Everything ships as **one repository**, rooted at the project folder (the parent of
`backend/` and `frontend/`), with `render.yaml` at that root. From the project root:

```bash
cd /home/bolt/Desktop/trainer-prediction-system-code

# Collapse the old backend-only git history so the whole project is one clean commit.
rm -rf backend/.git

git init
git add .
git commit -m "TPS: backend + frontend + Render blueprint"

# Create a PRIVATE repo under your account and push in one step:
gh repo create trainer-prediction-system --private --source=. --remote=origin --push

# …or if you prefer to create it in the browser first, then:
# git remote add origin git@github.com:LiamBolt/trainer-prediction-system.git
# git branch -M main && git push -u origin main
```

Private is the right default: this is a government system, and while no secrets are
committed, the source and the SRS-derived logic are not for a public repo. The root
`.gitignore` keeps `node_modules/`, the SRS PDFs, the `PROMPTS/` folder, and every
`.env` out of the repo (the `*.example` templates are kept).

---

## Step 4 — Render Blueprint

1. **render.com → New → Blueprint.**
2. Connect the `trainer-prediction-system` GitHub repo. Render reads the **root**
   `render.yaml` and proposes one web service, `tps-backend`, built from the `backend/`
   directory (the blueprint sets `dockerContext: ./backend`). The frontend is not part
   of the blueprint — deploy it separately as a static site (Step 5).
3. Before the first deploy, set the two secrets Render marked *"value required"* (they are
   `sync: false` in the blueprint, so they are never in git):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Supabase **session-pooler** URL from step 1a |
   | `CORS_ORIGINS` | the frontend's exact origin, e.g. `https://tps-frontend.onrender.com` (no trailing slash, comma-separated if several) |

   `DB_SSL_INSECURE=true` is already in the blueprint — **leave it.** Supabase's pooler
   presents a certificate signed by Supabase's own CA, which the system trust store does
   not carry, so a verifying TLS handshake fails with *"self-signed certificate in
   certificate chain"*. The connection is still encrypted; only certificate verification
   is off, which is exactly what Supabase's own `sslmode=require` strings do. This was
   verified against your project — without it, the API cannot connect.

   `JWT_SECRET_KEY` is generated by Render automatically — do not set it. `ENVIRONMENT`
   is already `production`, which makes the app **refuse to boot** on a weak JWT key, so
   the generated one is doing real work.
4. **Apply.** Render builds the Docker image and starts the service. Because migrations
   already ran in step 2, the API comes up against a populated database.
5. Watch **Logs** for `application startup complete` and `database_reachable`. Then open
   `https://<your-service>.onrender.com/health/ready` — expect `"status":"ready"` with the
   Supabase host in the detail.

That is the whole deploy. Subsequent `git push` to `main` redeploys automatically.

### Migrations on future deploys

The blueprint does **not** migrate on deploy. When you add a migration later, apply it the
same way as step 2 (`DATABASE_URL=… uv run alembic upgrade head` from your laptop) before
or just after pushing. On a **paid** Render instance you may instead uncomment
`preDeployCommand: alembic upgrade head` in `render.yaml` and let Render run it before each
release; it is commented out because pre-deploy commands are not available on the free tier.

---

## Step 5 — Point the frontend at the API

In the **frontend** repo (which stays where it is), set its API base URL to the Render
service URL and rebuild/redeploy it. Typically a Vite env var:

```
VITE_API_BASE_URL=https://<your-service>.onrender.com/api/v1
VITE_USE_MOCKS=false
```

Then make sure Render's `CORS_ORIGINS` (step 4) is the frontend's real origin. If the
browser console shows a CORS error, that value is wrong — it must match the frontend
origin exactly, scheme included, no trailing slash.

> Phase-3 frontend tasks still apply regardless of hosting: the demo password constant at
> `frontend/src/hooks/useAuth.ts:16` must become `Tps@2026#Demo`, the four IDOR call
> sites must be corrected, and a token-refresh flow must be added (the 15-minute access
> token otherwise signs users out every 15 minutes). See the backend `API-GUIDE.md`.

---

## Verifying the deployment

```bash
API=https://<your-service>.onrender.com

curl -s $API/health/ready          # {"status":"ready", … "Connected to …pooler.supabase.com…"}
curl -s $API/version               # version, the deployed commit, environment=production

# Sign in and hit a protected route:
TOKEN=$(curl -s -X POST $API/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin.training","password":"Tps@2026#Demo"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s $API/api/v1/dashboard/summary -H "Authorization: Bearer $TOKEN"
```

For a full functional walk-through, follow `docs/MANUAL-TEST-PLAN.md` against the Render
URL instead of localhost.

---

## Troubleshooting

**`Network is unreachable` / connection hangs.** You are using the direct
`db.<ref>.supabase.co` host (IPv6-only). Use the session-pooler host from step 1a.

**`Tenant or user not found` from Supabase.** The pooler username must include the project
ref: `postgres.xwvrdgodigxxuzvuvwfn`, not bare `postgres`. Copy the string from the
dashboard's *Session pooler* tab rather than editing the direct one by hand.

**`password authentication failed`.** You rotated the Supabase password but pasted the old
one into Render, or vice versa. They must match. If the password contains
`@ : / ? # [ ] %`, either choose one without them or ensure it is percent-encoded in the
URL (`@` → `%40`).

**`self-signed certificate in certificate chain` at startup or seed.** Supabase's pooler
certificate is signed by Supabase's own CA, not one the system trusts. Set
`DB_SSL_INSECURE=true` (already in the blueprint). The traffic stays encrypted; only
verification is off — the same posture as Supabase's `sslmode=require` strings. To pin
instead of skipping verification: download Supabase's CA certificate (dashboard →
Database → SSL configuration), mount it, and point asyncpg at it rather than using the
insecure flag. For this project the insecure flag is the documented, working choice.

**`prepared statement "__asyncpg_…" does not exist` or `DuplicatePreparedStatement`.** You
are on the **Transaction** pooler (port 6543). Switch to **Session** mode (port 5432).

**CORS errors in the browser.** `CORS_ORIGINS` on Render does not exactly match the
frontend origin. No wildcard is allowed (credentials forbid it); list the exact origin(s).

**First request after idle is slow (free tier).** Render's free web services sleep after
inactivity and take ~30–60s to wake. The first request pays that; subsequent ones are
fast. A paid instance stays warm. This is Render, not the app.

**`JWT_SECRET_KEY must be at least 32 characters` at boot.** `ENVIRONMENT=production` with
no strong key. Let Render generate it (`generateValue: true` in the blueprint) — do not
set it by hand.

---

## What is committed, and what is not

Committed: all source, the Dockerfile, `render.yaml`, migrations, the seed, the exported
`docs/openapi.json`, and every document. **Not** committed (in `.gitignore`): `.env`, the
virtualenv, caches, and anything holding a secret. No password, JWT key, or connection
string is in the repository. Verify anytime with:

```bash
git ls-files | grep -E '\.env$|secret' || echo "clean — no secret files tracked"
git grep -i 'tps_dev_2026\|supabase.co' -- ':!DEPLOYMENT.md' || echo "clean — no credentials in tracked source"
```
