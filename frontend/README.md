# Trainer Prediction System — Frontend

**Uganda Police Force · ICT Research, Planning & Innovation**

A decision-support frontend that replaces trainer selection by memory and phone calls
with evidence. When a course is scheduled, TPS scores every eligible trainer against
the requirements and hands the Training Administrator a **ranked, explained shortlist**
to approve.

The system does not make the decision. It makes the decision *defensible*.

React 18 · Vite 5 · TypeScript (strict) · Tailwind CSS v3 · Radix UI · TanStack Query · Zustand

---

## 1. Setup

```bash
cd frontend
npm install
npm run dev
```

Node 20+. The app starts at `http://localhost:5173` and **needs no backend** — it runs
against a seeded, deterministic mock data layer.

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` | Typecheck + production build |
| `npm run preview` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (zero warnings enforced) |
| `npm test` | Vitest (scoring engine, mock data, re-rank) |

---

## 2. Demo accounts

All four accounts use the password **`Demo@2026`**. They are also listed on the sign-in
screen behind the "Demo accounts" disclosure (visible only when `VITE_USE_MOCKS=true`),
each with a one-click fill button.

| Role | Username | Name |
|---|---|---|
| Training Administrator | `admin.training` | SSP Grace Nabirye |
| Training Officer | `officer.training` | ASP Joseph Okello |
| Trainer | `trainer` | IP Sarah Mugisha |
| System Administrator | `sysadmin` | SP Denis Byaruhanga |

A **DEMO ROLE** switcher in the top bar (mocks only) jumps between roles without
signing out.

**Sign-in behaviour (FR-01):** three consecutive failures lock the account for 15
minutes, showing a live countdown that survives a page reload. The system never
reveals whether a username exists.

---

## 3. Environment variables

`.env.example` (copy to `.env`):

```
VITE_API_URL=http://localhost:8000/api
VITE_USE_MOCKS=true
VITE_MOCK_LATENCY_MS=420
VITE_APP_VERSION=1.0.0
```

### Switching to the real backend

Set **`VITE_USE_MOCKS=false`**. That is the only change required — no code edits.

The mechanism is one line in `src/api/axiosClient.ts`:

```ts
if (USE_MOCKS) {
  client.defaults.adapter = mockAdapter;
}
```

Every screen calls the typed functions in `src/api/endpoints/*`, whose signatures are
final and identical in both modes. Turning mocks off simply stops swapping the Axios
adapter, so the same requests go over HTTP to `VITE_API_URL`.

---

## 4. Folder map

```
frontend/src/
├── api/
│   ├── axiosClient.ts        # the single Axios instance + interceptors
│   ├── mockAdapter.ts        # ONLY thing bypassed when mocks are off
│   └── endpoints/            # typed service layer (final signatures)
├── app/
│   ├── router.tsx            # data router, lazy routes, guards
│   └── providers.tsx         # Query, Tooltip, Toaster, Router
├── components/
│   ├── ui/                   # primitives (Radix + Tailwind, cva variants)
│   ├── layout/               # AppShell, Sidebar, TopBar, PageHeader, ClassificationBar
│   ├── prediction/           # the explainability suite (§12)
│   ├── charts/               # TrendLine, DistributionBar (lazy-loaded recharts)
│   ├── table/                # DataTable (TanStack Table), FilterBar
│   ├── routing/              # ProtectedRoute, RoleGate
│   └── feedback/             # ErrorBoundary, RouteSkeleton
├── features/                 # one folder per screen area
├── lib/
│   ├── scoring/              # ← THE SCORING MODEL (see below)
│   ├── rerank.ts             # client-side Weight Studio re-rank
│   ├── constants.ts          # ranks, criteria, stations, presets
│   ├── format.ts             # every numeral/date formatter
│   ├── csv.ts / pdf.ts       # exports
│   └── nav.ts                # role-filtered navigation model
├── mocks/
│   ├── seed.ts               # mulberry32 PRNG (fixed seed 20260722)
│   ├── data/generate.ts      # the whole seeded world
│   └── handlers.ts           # request resolvers (the mock "backend")
├── stores/                   # auth, theme, ui, weight (Zustand)
├── schemas/                  # Zod schemas per form
├── types/                    # domain.ts (the SRS ERD), api.ts
└── styles/globals.css        # design tokens, both themes
```

---

## 5. Where the scoring model lives

**`src/lib/scoring/`** — pure functions, zero React, fully unit-tested.

| File | Stage |
|---|---|
| `gates.ts` | **Stage 1** — hard gates (elimination, not scoring) |
| `criteria.ts` | **Stage 2** — per-criterion normalisation to 0–100 |
| `score.ts` | **Stage 3** — totals, confidence, deterministic tie-break |
| `narrative.ts` | **Stage 4** — the rationale sentence and counterfactual |
| `index.ts` | Orchestrator: `runPrediction()` → a full `PredictionRun` |

This is a **transparent weighted multi-criteria model**, not machine learning. Nothing
in the interface claims otherwise.

**Default weights:** Specialisation 30 · Performance 25 · Experience 20 ·
Qualification 15 · Availability 10 (always totalling 100).

**Hard gates**, applied in order — the first failure is the recorded reason:
1. Marked unavailable → **BR-03**
2. Missing the required specialisation → **BR-04**
3. Schedule conflict with a confirmed allocation
4. Below the minimum experience → FR-05
5. Below the minimum qualification → FR-05

Excluded trainers **never appear in the ranked list**, but every one of them is
inspectable in the Exclusion Ledger.

**An honest detail:** a trainer with no evaluations receives a *neutral prior of 55*,
not a zero — they are not punished for a system that has no history yet. Wherever that
happens, the interface says so.

**Key property used by the Weight Studio:** changing weights never changes a
criterion's `normalized` value — only its `contribution` and the total. So re-ranking
is a pure recompute (`lib/rerank.ts`), instant and client-side.

---

## 6. Demo walkthrough

The exact click path, with the numbers this seeded dataset actually produces:

1. Open **`/`** — the landing page (one viewport, no scrolling).
2. Sign in as **`admin.training`** / `Demo@2026`.
3. The dashboard shows **3 predictions ready** and a prediction queue.
4. Open **Basic Cybercrime Investigation Course — Intake 14**.
5. The ranked list loads: **812 considered · 114 excluded · 698 ranked · computed in 1.4s**.
   Rank 1 is distinguished with a glass surface and a TOP RANKED eyebrow.
6. Rank 1 is **IP Sarah Mugisha (90.1)**; rank 2 is **ASP Betty Nabirye (89.6)** — within
   1.4 points, which makes the weighting genuinely consequential.
7. Select rank 2 and read its ledger, rationale, and counterfactual.
8. Expand the **Exclusion Ledger** and see named trainers grouped by the rule that
   excluded them (BR-03, BR-04, FR-05).
9. Open the **Weight Studio**, apply *Prioritise proven performance* — rows physically
   re-order and the top rank changes from Mugisha to Nabirye. The summary states the
   consequence in words.
10. **Reset to policy**, then **approve rank 1** — the confirm dialog restates the
    trainer, programme, score, and rank (BR-06).
11. Read the **Decision Receipt** with its registry number `TPS/ALL/2026/…`, the frozen
    score breakdown, and the weighting in force.
12. Switch to **`trainer`** — the invitation appears, showing *why* they were selected.
    Decline with a reason (Submit stays disabled until one is written).
13. Back as **`admin.training`**, open the declined allocation and **promote the
    next-ranked candidate** — the panel states plainly that the original ranking is
    reused and no new prediction is run.
14. Open a conducted course and **record an evaluation**; the toast says the score now
    informs future rankings.
15. Open **Reports**, filter, and export a PDF (always light-theme) or CSV.
16. Switch to **`sysadmin`** — the **audit log** shows every one of those actions with
    timestamps, marked `IMMUTABLE RECORD`.
17. Toggle **dark mode** and walk it again.

---

## 7. Notes

- **Accounts are never self-created.** There is no sign-up anywhere; "Need access?" is
  an instruction to contact the System Administrator, not a form (D3).
- **UI gating is convenience, not security.** `ProtectedRoute` and `RoleGate` both carry
  that comment — the API enforces authorisation server-side (NFR-04).
- Design decisions, tokens, and every deliberate deviation are recorded in
  **`DESIGN-NOTES.md`**.
