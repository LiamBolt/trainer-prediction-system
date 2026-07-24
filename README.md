# Trainer Prediction System (TPS)

A decision-support system for the Uganda Police Force that ranks trainers for
training programmes using weighted multi-criteria analysis (not machine
learning), with a full audit trail and role-based access control.

This repository holds **both halves of the project plus the deployment blueprint**:

```
trainer-prediction-system/
├── backend/          FastAPI + PostgreSQL API (Dockerised)   → deploys to Render
├── frontend/         React + Vite single-page app            → deploy as a static site
├── render.yaml       Render Blueprint (builds the backend from ./backend)
├── README.md         you are here
└── .gitignore        root-level ignores
```

The **database** is not in this repo — it runs on **Supabase** (managed
PostgreSQL). The backend reaches it over the Supabase *session pooler*; see
`backend/DEPLOYMENT.md`.

## The three moving parts

| Part | Lives in | Hosted on | Talks to |
|---|---|---|---|
| Frontend (static SPA) | `frontend/` | any static host (Render Static Site, Vercel, Netlify) | the backend, over HTTPS |
| Backend (API) | `backend/` | Render (Docker web service, from `render.yaml`) | Supabase, over TLS |
| Database | — | Supabase | — |

Three env values wire it together: the frontend's `VITE_API_URL` → the backend
URL; the backend's `CORS_ORIGINS` → the frontend origin; the backend's
`DATABASE_URL` → the Supabase session-pooler URL.

## Running it locally

Each subproject documents its own workflow — start there:

- **Backend:** `backend/RUNBOOK.md` (which terminals to open, the local Postgres,
  seeding, running the API and tests).
- **Frontend:** `frontend/README.md` (install, `npm run dev`, mock vs. live API).

Local development is unaffected by the deployment config: with no `DATABASE_URL`
set, the backend talks to your local PostgreSQL exactly as before.

## Deploying

- **Backend + database:** follow `backend/DEPLOYMENT.md` end to end (Supabase
  setup, GitHub, Render Blueprint). Render reads `render.yaml` at this repo root
  and builds the image from `backend/`.
- **Frontend:** build with Vite (`npm run build` in `frontend/`) and serve the
  `dist/` output from any static host; point it at the deployed backend URL and
  add that origin to the backend's `CORS_ORIGINS`.

## Testing it yourself

`backend/docs/MANUAL-TEST-PLAN.md` is a full functional walk-through — point it at
your deployed API and tick through every feature.
