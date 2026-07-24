# TPS Frontend — Design Notes

Living record of the token system, conventions, and every deliberate deviation
from `TPS-FRONTEND-MEGA-PROMPT.md`, with the reason. Expanded per phase.

## Token system (§4)

- **Colour**: the fixed `primary-50..900` navy scale is set as literal hex in
  `tailwind.config.ts` (identical in both themes, D10). Theme-varying surfaces,
  text, and brand tokens are CSS custom properties in `src/styles/globals.css`,
  stored as **space-separated RGB channels** so Tailwind's
  `rgb(var(--x) / <alpha-value>)` colours resolve with alpha. Tokens that carry
  baked-in alpha (borders, glass, overlay, semantic tints, viz ramp, elevation)
  are stored as full CSS values and referenced with `var(--x)` directly.
- **Semantic + viz** colours are CSS vars so they can differ per theme; exposed
  as `success/warning/danger/info` (`fg`/`bg`/`border`) and `viz-1..5`.
- **Elevation** `e1/e2/e3` are CSS vars (`--shadow-e1..3`) that switch between
  the light shadow stack and the dark inset-highlight stack automatically.

## Type scale (§4.3)

All 13 tokens are registered in `fontSize` with exact size/line/tracking/weight:
`display-lg, display, h1, h2, h3, body-lg, body, body-sm, caption, label, data,
data-lg, data-xl`. `label` and `data*` are JetBrains Mono; body is Open Sans;
headings are Roboto. Global `tabular-nums` is set on `html`/`body`.

## Spacing convention (§4.4, §5) — IMPORTANT

Tailwind's numeric class is a **scale index, not a pixel value**. The legal px
values `{4,8,12,16,20,24,32,40,48,64,80}` map to classes
`{1,2,3,4,5,6,8,10,12,16,20}`. Only these are used for padding / gap / margin.
Avoid `p-7 (28), p-9 (36 as padding), p-11 (44), p-14 (56)` for layout spacing.
Fixed component dimensions are exposed as named spacing tokens to avoid arbitrary
values: `h-row (52), h-badge (22), w-sidebar (264), w-sidebar-collapsed (72),
h-app-bar (64), h-classification (28)`. Button heights use `h-8/9/10 (32/36/40)`.

## Glass allowlist (§4.5)

`.glass` utility lives in `globals.css` with a `@supports not (backdrop-filter)`
fallback raising alpha to `.94`. Permitted surfaces only: top app bar (dark),
Dialog panel + backdrop, mobile sidebar overlay, command palette, notification
popover + user menu, the rank-1 prediction card, and the landing sign-in card.

## Deliberate deviations / clarifications

- **`Allocation.frozenWeights` + `weightsWereSimulated`** added to the domain
  model (§6). The Decision Receipt (§12.7) must show "the weights in force" and
  the approval flow (§12.6) must record whether simulated weights were used;
  these fields carry that. Not a contradiction of the SRS — an additive detail.
- **Inputs are 40px tall** (`h-10`) with **14px horizontal padding** (`px-3.5`,
  a real Tailwind step) — a faithful realisation of §5.2's "12px vertical, 14px
  horizontal" within the fixed-height system, aligned to the `lg` control height.
  Multi-line `Textarea` uses the exact `py-3 px-3.5` (12/14).
- **Arbitrary-value exceptions** that are *not* magic spacing and are considered
  justified for the §17.4 audit: (a) Radix positioning CSS variables such as
  `w-[--radix-popover-trigger-width]` and `max-h-[--radix-select-content-available-height]`;
  (b) grid templates like `grid-cols-[minmax(0,140px)_1fr]` in `KeyValueList`.
  No hardcoded pixel magnitudes are used via bracket syntax.
- **Status/tone dot** on `Badge` is 6px (`h-1.5 w-1.5`) — a sub-scale decorative
  detail, not layout spacing; passes the `-[` grep.

## Scoring engine (§7)

Pure, React-free, in `src/lib/scoring/` (gates → criteria → score → narrative →
index orchestrator). 21 unit tests. Key property exploited by the Weight Studio:
changing weights never changes a criterion's `normalized` value — only its
`contribution` and the total — so re-ranking is a lightweight `recomputeWithWeights`
over the existing breakdown, not a re-score. Normalisation is rounded to 2 dp at
source to keep it float-noise-free and deterministic.

## Mock dataset (§8) — demo-data choices

Deterministic (mulberry32, seed 20260722), verified by 11 tests. Two deliberate
seed-distribution choices so the documented demo (§11.4/§18) holds:
- Cybercrime Investigation is a **common** specialisation (~93% of trainers,
  skewed to BASIC/INTERMEDIATE) because the hero course is a *basic* course — this
  yields the large ranked pool the spec's headline numbers imply, while four
  curated "hero" trainers stay the clear top of the ranking.
- The extra evaluation history is given to non-Investigations specialists so no
  random trainer gains *relevant* performance in the featured cybercrime run,
  keeping IP Mugisha #1 and ASP Nabirye #2 (within ~1.4 pts) as the spec requires.

## Service layer (§9.3)

`client.defaults.adapter = mockAdapter` is the ONLY line gated on VITE_USE_MOCKS —
turning mocks off is a single `.env` change, no code edits. Endpoint signatures
are final. The mock handlers mutate the in-memory db so the full walkthrough
(approve → decline → promote-next → evaluate) works and writes audit entries.

## Routing note (bug fixed)

A pathless protected-layout route with an `index` child **also matches "/"** and
shadowed the public LandingPage (its ProtectedRoute bounced "/" to /signin). Fix:
no index route under the AppShell layout; LandingPage itself redirects an
authenticated visitor to /dashboard. Verified by headless-Chrome screenshots.

## §17 self-audit results

Automated checks (run from `frontend/`):

| Check | Result |
|---|---|
| `tsc --noEmit` | **0 errors**; zero `any`, zero `@ts-ignore` |
| `eslint . --max-warnings 0` | **0 errors, 0 warnings** |
| `vitest run` | **35 passing** (scoring 21, mock data 11, re-rank 3) |
| `vite build` | passes; initial JS **233 KB gzip** (target < 300 KB), CSS 8.4 KB gzip |
| `console.log` in `src/` | **none** |
| Hardcoded `text-white`/`bg-white`/`gray-*`/`slate-*` | **none** |
| Glass usage | confined to the seven §4.5 surfaces (verified by grep) |
| Table rows / badges | `h-row` (52px) and `h-badge` (22px) tokens; cells `whitespace-nowrap` |

**Defects found and fixed during the audit:**
1. **Badges wrapped and overflowed** their fixed 22px pill in table cells → added
   `whitespace-nowrap leading-none` to `Badge`.
2. **Table rows exceeded the mandated 52px** because cell text wrapped → cells are now
   `whitespace-nowrap` with `truncate` on long text columns; the table scrolls
   horizontally rather than growing taller.
3. **Dark-mode contrast bug:** the danger button and the notification count used
   `text-white` on `--danger-fg`, which is a *light* red in dark mode (white-on-light-red
   fails AA). Both now use `text-canvas`, which inverts with the theme.
4. **Router bug:** a pathless protected layout route with an `index` child also matched
   `/` and shadowed the public landing page. Removed the index route.

**Remaining bracketed values are justified, not magic numbers:** Radix variant selectors
(`data-[state=…]`), Radix positioning variables (`w-[--radix-popover-trigger-width]`),
grid templates (`grid-cols-[…]`), CSS property lists (`transition-[transform,box-shadow]`),
and `hover:-translate-y-[2px]`, which §4.4 specifies verbatim. Named tokens were added for
everything else (`h-row`, `h-badge`, `w-sidebar`, `h-dvh`, `min-h-panel`, `min-w-menu`,
`grid-cols-predict`, `max-w-content/form/card`).

**Not verified in this pass (requires manual/interactive QA):** full keyboard-only
walkthrough (§17.18), contrast measured with a tool over the landing video's brightest
frame (§17.15 — the clip is still pending from the client), and screenshots of every
screen at 1280/1440/1920 in both themes (§17.1, §18.5). Key screens were verified by
headless-Chrome screenshot at 1440 in both themes, with pixel sampling confirming the
dark canvas is `#0f0d2e`.

## Build status

- Phase 1 complete: tokens, both themes, fonts, primitives, `/kitchen-sink`.
- Phase 2 complete: scoring engine + 21 tests, seeded data + 11 tests, service
  layer + mock adapter, TanStack Query, Zustand stores (auth/ui/theme/weight).
- Phase 3 complete: landing (§13.1), sign-in + lockout (§13.2), AppShell / Sidebar
  / TopBar / PageHeader / ClassificationBar, data router + guards, command palette,
  theme toggle, error pages.
- Phase 4 complete: the prediction centrepiece (§11.4) and the full explainability
  suite (§12) — Score Ledger, criterion rows, rationale, confidence with the honest
  low-data note, counterfactual, Exclusion Ledger, Decision Receipt, and the Weight
  Studio with FLIP re-rank (framer-motion `layout`, reduced-motion aware).
- Phase 5 complete: programmes (list → create → requirements → detail), allocations +
  Decision Receipt with promote-next, trainer directory/profile, trainer self-service
  (profile, credentials, assignments, performance), evaluations.
- Phase 6 complete: role-adaptive dashboards, three reports with PDF/CSV export,
  users/roles, virtualised audit log, system health, scoring policy, notifications,
  settings.
- Phase 7 complete: route-level code splitting (React.lazy + Suspense with a
  route-shaped skeleton), §17 audit and fixes, README, these notes. The dev-only
  screenshot helper (`public/__dev_login.html`) has been **deleted**.
