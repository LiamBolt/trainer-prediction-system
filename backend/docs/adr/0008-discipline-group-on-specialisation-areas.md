# ADR-0008 — `discipline_group` on `specialization_areas`

**Status:** Accepted · 2026-07-23
**Arises from:** conflict C2 in `PROGRESS.md`

## Context

`02-DATABASE-PROMPT.md` §5.1 specifies `training_categories` seeded with a
**delivery-mode** taxonomy: Initial Training, Refresher, Specialised Skills, Command
and Leadership, Induction, Pre-Deployment, Regional/International, Instructor
Development.

The frontend's `TrainingProgramme.category` carries something different — a **subject**
taxonomy: Investigations, Forensics, Traffic, Community Policing, Public Order, and so
on. That value is load-bearing in the scoring engine in two places:

- `frontend/src/lib/scoring/criteria.ts:71-76` — the SPECIALIZATION **+10 breadth
  bonus** fires when a trainer's *second* specialisation maps to the same category as
  the programme.
- `frontend/src/mocks/data/generate.ts:542-543` — the PERFORMANCE **relevance test**
  counts a past evaluation as relevant when its programme shares this programme's
  category. §5.10 requires the view to expose "count of evaluations within the required
  specialisation", which is the same question.

Seeding §5.1's category list and changing nothing else leaves both rules with no
input. They would not error; they would quietly stop firing, and Phase 2 could not
reproduce the frontend's scores.

## Decision

Keep `training_categories` exactly as §5.1 specifies, and add a nullable
`discipline_group VARCHAR(60)` column to `specialization_areas`, seeded with the
frontend's `SPECIALIZATION_CATEGORY` values.

A programme's subject group is derived through
`required_specialization_area_id → discipline_group`.

## Alternatives considered

**Replace `training_categories` with the subject taxonomy.** Simplest, and makes the
frontend work unchanged. Rejected because it discards a real distinction the UPF
makes: "Refresher" and "Investigations" are orthogonal, and a Refresher course *about*
Cybercrime Investigation is a normal thing to run. Conflating them would make the
category field unable to express either idea properly.

**Add a second FK from `training_programmes` to a new `discipline_groups` table.**
Fully normalised, and a group would gain a description. Rejected as redundant: a
programme already points at its required specialisation area, and the group is a
property of that discipline, not an independent choice. Two FKs would permit the
contradictory state of a Forensics programme requiring a Traffic specialisation.

**Compute the grouping in application code from a Python dictionary.** This is what
the frontend does. Rejected for the reason §5.1 gives for making specialisation a
table at all: a hard-coded map fails silently on a spelling variant, and a newly added
specialisation is invisible to both rules until someone remembers to edit the constant.

## Consequences

- Both scoring rules keep a foreign-key-backed input, so they cannot fail on a string
  mismatch.
- `discipline_group` is nullable. `NULL` means ungrouped, and neither rule fires — a
  safe default rather than a silent misfire. `DRAFT` programmes have no requirement set
  and are never scored, so the nullability costs nothing.
- The view exposes `evaluations_by_discipline_group` and `mean_by_discipline_group` as
  JSONB maps, answering §5.10's requirement without changing the view's grain.
- Phase 3 should reconcile `frontend/src/lib/constants.ts` so `SPECIALIZATION_CATEGORY`
  is read from the API rather than duplicated.
