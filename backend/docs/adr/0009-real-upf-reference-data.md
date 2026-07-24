# ADR-0009 — Real UPF reference data over the frontend's mock lists

**Status:** Accepted · 2026-07-23 (decision confirmed by the project owner)
**Arises from:** conflict C1 in `PROGRESS.md`
**Deviates from:** D9

## Context

Two sources disagree about the organisational vocabulary.

| Vocabulary | §5.1 of the specification | `frontend/src/lib/constants.ts` |
|---|---|---|
| Regions | 29 real policing regions (KMP East, Albertine North, Aswa West, …) | 7 broad labels (Central, Eastern, Northern, …) |
| Directorates | 17 real directorates | 12, partly renamed |
| Stations | ~31 plus 8 named training institutions | 29, shortened names |
| Institutions | 22, typed POLICE/UNIVERSITY/PROFESSIONAL/INTERNATIONAL | 13, untyped |
| Specialisation areas | 24 | 24 — identical |

D9 requires the seed to mirror the frontend mocks so that flipping
`VITE_USE_MOCKS=false` yields a visually identical application. §5.1 enumerates the
real lists explicitly. Both cannot be satisfied.

## Decision

Seed the **real §5.1 lists**. `frontend/src/lib/constants.ts` is updated in Phase 3.

This was raised as an open question before any code was written and confirmed by the
project owner rather than decided unilaterally.

## Alternatives considered

**Mirror the mock lists exactly, honouring D9 literally.** Zero frontend change, and
the mock-to-API switch is invisible. Rejected because §7 states the seed must
"withstand a Training Directorate officer reading it and recognising their own
organisation" — and an officer reading "Central Region" where the UPF has KMP East,
Katonga, and Savannah will not recognise it. The demo's credibility with its actual
audience outweighs a cosmetic diff during a transition.

**Seed the real lists with an alias column carrying the mock label.** Both render.
Rejected: it adds a column whose only purpose is to paper over a transitional
mismatch, and it would outlive the transition, as such columns do.

**Defer the decision and seed only the overlap.** Rejected as the worst option — it
produces reference data that is neither real nor mock-compatible.

## Consequences

- **No TypeScript contract breaks.** `domain.ts` types `region`, `directorate`,
  `station`, and `institutionName` as plain `string`; only rendered literals differ.
  This is what makes the deviation safe, and it was verified before deciding.
- Phase 3 must update `constants.ts`: `REGIONS`, `DIRECTORATES`, `STATIONS`, and
  `INSTITUTIONS`. The `POLICE_INSTITUTIONS` set can be deleted entirely, since
  `institutions.institution_type` now carries that fact structurally.
- Filter dropdowns driven by the frontend constants will show stale options against a
  live API until Phase 3 lands. This is the concrete, temporary cost.
- 24 specialisation areas match exactly, so BR-04 — the rule that most depends on
  vocabulary agreement — is unaffected either way.
