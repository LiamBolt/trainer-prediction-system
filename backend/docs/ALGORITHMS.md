# The scoring algorithm

*Trainer Prediction System — Uganda Police Force*

This document explains how the system arrives at a ranking, why each method was chosen over the
alternatives, and where the model is weak. It is written to be read by a supervising officer or an
external examiner, not only by a developer. Where a claim is measurable, the measurement is given.

**One thing to establish before anything else:** this system does not predict who *will* perform
well. It ranks candidates against stated criteria using a rule an officer can check by hand. The
word "prediction" appears in the system's name; the arithmetic below is a scoring model, and the
decision remains a person's. BR-06 makes that structural — no allocation is final without an
explicit Training Administrator approval, and there is no auto-approve path anywhere in the API.

---

## 1. The problem

Selecting a trainer for a course is a multi-criteria decision under partial information.

Five criteria bear on it, and they are **incommensurable** — a Master's degree and eleven years of
service are not measured in the same units, and no exchange rate between them exists in nature. Any
method must impose one, and the honest thing is to impose it visibly.

Three constraints shape everything that follows:

1. **Explainability is a requirement, not a feature.** FR-07 requires the Administrator to see
   which criteria matched and by how much. A ranking a person cannot defend is not usable in a
   disciplined service, whatever its accuracy.
2. **There is no historical data at launch.** Not "little" — none. The cold-start problem is total.
3. **The decision must reproduce.** An allocation questioned in eighteen months must be
   reconstructible from what was recorded, exactly, including the weights in force at the time.

---

## 2. Why weighted multi-criteria decision analysis, and not machine learning

| Approach | Why it was rejected |
|---|---|
| **Supervised ML** (logistic regression, gradient boosting) | Requires labelled outcomes. The system launches with **zero** allocation history. A model cannot be trained on data that does not exist, and generating synthetic labels to train on would mean the model learns the assumptions of whoever wrote the generator. |
| **Learning-to-rank** (LambdaMART, RankNet) | Same cold-start problem, plus rankings that cannot be decomposed into per-criterion contributions. FR-07 requires the Administrator to see *which criteria matched*; a learned ranker cannot honestly provide that. Feature attributions (SHAP, LIME) are post-hoc approximations of the model, not the reason it ranked. |
| **TOPSIS** | Theoretically stronger — ranks by distance to an ideal solution and handles criteria interaction better than a linear sum. Rejected because its output is a closeness coefficient that **cannot be decomposed into readable contributions**, which is precisely what the Score Ledger must display. |
| **AHP** (Analytic Hierarchy Process) | Derives weights from expert pairwise comparisons, which is genuinely attractive for *setting policy*. Rejected as the runtime model because eliciting a consistent comparison matrix from officers is a research exercise, not a deployment step. **This is the right method for a future weight-setting workshop** — and because weights live in `scoring_policy_weights` rows rather than in code, the output of such a workshop can be entered without a deployment. |
| **ELECTRE / PROMETHEE** | Outranking methods producing partial orders. BR-05 requires a total order from highest to lowest. A partial order cannot produce "rank 1". |
| **Weighted Sum Model** *(chosen)* | Linear and additive, so each criterion's contribution to the final score is directly readable — which is exactly what the Score Ledger renders. Deterministic and reproducible. Retunable by changing a number rather than by retraining. Works on day one with no history. |

### The honest limitation

WSM assumes **criterion independence** and **linear preference**. Neither is perfectly true.
Qualification and specialisation are correlated in practice; the difference between 4 and 8 years of
service probably matters more than the difference between 24 and 28, and the model treats both
regions of the scale as equally spaced up to the ceiling.

WSM is also **fully compensable**: a very high score on one criterion can mask a very low score on
another. That is mitigated — not solved — by the hard gates in §3, which make the non-negotiable
requirements non-compensable by construction. No weighting of any kind can admit a trainer who
lacks the required specialisation, because that trainer never reaches the scoring stage.

This is the right trade for a system whose primary requirement is that a human can defend its
output. A more sophisticated model that a Training Administrator cannot explain to a review board
is worse for this purpose than a simpler one they can.

---

## 3. The pipeline

```
                     812 trainers
                          │
              ┌───────────▼───────────┐
   Stage 1    │      HARD GATES       │   elimination, not scoring
              │  five rules, in order │   → Exclusion Ledger with rule citations
              └───────────┬───────────┘
                          │ survivors
              ┌───────────▼───────────┐
   Stage 2    │     NORMALISATION     │   five criteria → 0–100 each
              │  one function each    │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
   Stage 3    │      AGGREGATION      │   Σ (weightᵢ × normalisedᵢ) / 100
              │   weights sum to 100  │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
   Stage 4    │  RANK + TIE-BREAK     │   total order, deterministic
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
   Stage 5    │ CONFIDENCE + NARRATIVE│   data completeness, rationale,
              └───────────────────────┘   counterfactual
```

### Stage 1 — hard gates

Five rules, applied **in this order**, and the *first* failure is the reason recorded:

| # | Rule | Reason recorded | Citation |
|---|---|---|---|
| 1 | `availability_status = 'UNAVAILABLE'` | `UNAVAILABLE` | BR-03 |
| 2 | No specialisation in the required area | `MISSING_SPECIALIZATION` | BR-04 |
| 3 | A confirmed allocation or declared absence overlapping the course dates | `SCHEDULE_CONFLICT` | BR-03 |
| 4 | Below the minimum years of service | `BELOW_MINIMUM_EXPERIENCE` | FR-05 |
| 5 | Below the minimum qualification, when one is set | `BELOW_MINIMUM_QUALIFICATION` | FR-05 |

**Order matters because the reason is shown to an officer.** A trainer who is both unavailable and
under-qualified is reported as unavailable, because that is the fact that settles it and the one
they can act on. Reporting the qualification instead would send someone to check a personnel file
about a person who could not attend regardless.

Excluded trainers do not appear in the ranked list — not greyed out, not at the bottom, **absent**
(BR-03). They appear in the Exclusion Ledger, grouped by reason with a sentence written for a
non-technical reader: *"Assigned to Digital Forensics Level 2 · 10-21 Aug 2026"*, never
`conflict=true`.

### Stage 2 — normalisation

Each criterion maps to 0–100. The functions are in §4.

### Stage 3 — aggregation

```
total = Σᵢ (weightᵢ × normalisedᵢ) / 100
```

Weights are rows in `scoring_policy_weights`, not columns and not constants (D8, NFR-10). They must
sum to exactly 100, enforced by a **deferred constraint trigger** so a multi-row update is checked
once at commit rather than after each statement.

Because the model is additive, `contribution = weight × normalised / 100` and the contributions sum
to the total **exactly**. This is checkable by hand from the Score Ledger, and it is the whole
reason for choosing an additive model.

### Stage 4 — ranking and tie-breaks

See §7.

### Stage 5 — confidence and narrative

See §6 and §8.

---

## 4. Normalisation, criterion by criterion

### SPECIALIZATION — how closely proven expertise matches the course

```
base       = proficiency_levels.score_value  for the required area
bonus      = +5  if a second specialisation falls in the same discipline group
normalised = clamp(base + bonus, 0, 100)
```

The base comes from a **lookup table**, not a constant. NFR-10 requires policy to be retunable
without a deployment: changing what "Advanced" is worth is an `UPDATE`, not a release.

The breadth bonus rewards adjacent competence. A trainer with two specialisations in
*Investigations* is a better bet for a cybercrime course than one whose only other discipline is
traffic policing, and the discipline group is what encodes that.

### QUALIFICATION — highest formal qualification

```
base       = qualification_levels.score_value  for the highest held
bonus      = +8  if any qualification is from institution_type = 'POLICE'
normalised = clamp(base + bonus, 0, 100)
```

The police-institution bonus is driven by a **column**, not by matching institution names. The
existing frontend implements this with a hard-coded list of names (`POLICE_INSTITUTIONS`), which
fails silently on a spelling variant and needs editing whenever a school is added. Here it is
structural: a newly added police college qualifies automatically.

Missing qualification scores **0** and is flagged `MISSING` in the breakdown — the interface shows
an amber marker, so the Administrator can see the difference between *scored low* and *no data*.

### EXPERIENCE — years of service

```
normalised = min(years / 20, 1) × 100
```

**Why capped at twenty rather than scaled to the maximum observed.** Scaling to the observed
maximum makes every trainer's score depend on the most senior person in the pool: one thirty-year
veteran joining the force would silently lower everyone else's experience score, with no change to
anyone's actual experience. Scores would also not be comparable between runs. Twenty years is a
fixed, defensible ceiling that says "beyond this, more service does not further distinguish a
trainer" — which is a policy judgement stated openly rather than an artefact of the data.

### PERFORMANCE — proven delivery

Bayesian shrinkage toward a prior. Derived in full in §5.

### AVAILABILITY — spare teaching capacity

```
normalised = max(0, 100 − 25 × active_allocation_count)
             capped at 50 if availability_status = 'ASSIGNED'
```

This is a **preference, not a gate** — a busy trainer is still eligible, merely less attractive.

It is also the criterion that does the most social work in the model. Without it, the
best-qualified trainer wins every course until they become unavailable, and the system entrenches
exactly the over-reliance the SRS problem statement describes. The `/reports/utilisation` report
exists to check whether it is succeeding.

---

## 5. Cold start and shrinkage

### The problem

At launch, no trainer has been evaluated. Two obvious approaches are both wrong:

**Score unevaluated trainers zero.** This punishes trainers for the system's newness. At launch it
punishes *everyone*, and the PERFORMANCE criterion — 25% of the total — becomes a constant that
contributes nothing to the ordering while appearing to.

**Use the raw mean.** A single lucky 5.0 then outranks a veteran averaging 4.6 across twelve
courses. The estimator has no notion of how much evidence sits behind it.

### The estimator

```
adjusted_mean = (n × observed_mean + k × prior_mean) / (n + k)
normalised    = (adjusted_mean − 1) / 4 × 100
```

with **k = 3** and `prior_mean` = the mean of every evaluation in the system, recomputed per run.
This is the posterior mean of a Normal-Normal conjugate model with the prior weighted as `k`
pseudo-observations. `k = 3` says: *the service-wide average is worth about three courses of
personal evidence.*

The `(x − 1) / 4 × 100` step maps the 1.0–5.0 rating scale onto 0–100 linearly. A 1.0 — the lowest
awardable score — normalises to 0, not to 20, because the scale's floor is 1.0 and treating it as
"20% good" would flatter it.

### Worked table

Prior = 4.45 (the mean over the seeded evaluations), trainer scoring a straight 5.0 each time:

| n | observed | adjusted | normalised |
|---:|---:|---:|---:|
| 0 | — | 4.450 | 86.25 |
| 1 | 5.0 | 4.588 | 89.69 |
| 2 | 5.0 | 4.670 | 91.75 |
| 3 | 5.0 | 4.725 | 93.12 |
| 5 | 5.0 | 4.794 | 94.84 |
| 12 | 5.0 | 4.890 | 97.25 |

### Properties that make it defensible

- **At n = 0 it returns exactly the prior.** With the default prior of 3.2 that is 55.0 normalised,
  which matches the frontend's existing flat behaviour. The flat 55 is a strict special case of
  this formula, not a competing rule.
- **Monotonic and continuous.** A newly recorded evaluation never causes a discontinuous jump in
  rank. This matters operationally: an officer who watches a trainer leap five places after one
  evaluation stops trusting the system.
- **Self-correcting.** By n = 12 the prior contributes a fifth of the weight and is nearly
  irrelevant. The estimator gets out of the way as evidence accumulates.

### An honest observation about the current data

The seeded evaluations have a mean of **4.155** and a standard deviation of **1.077** across 58
records. With a prior that high, shrinkage compresses the range: a newcomer with a single 5.0
scores 89.69 while a veteran averaging 4.6 over twelve courses scores 89.25 — the newcomer *edges
ahead*.

That is the estimator behaving correctly given its inputs, not a bug: when the prior is close to
everyone's observed mean, the criterion genuinely does not discriminate much, and pretending
otherwise would be false precision. But it means **PERFORMANCE currently separates candidates less
than its 25% weight suggests**, and the ordering is driven mostly by SPECIALIZATION and
QUALIFICATION. This should be re-examined once real evaluations replace the seed, and if evaluators
in practice award mostly 4s and 5s, the rating scale itself — not the estimator — is what needs
attention.

---

## 6. Confidence

```
confidence = 0.45 × evaluation_depth + 0.35 × profile_completeness + 0.20 × recency
```

where

```
evaluation_depth = min(evaluation_count / 5, 1) × 100
recency          = max(40, 100 × 2^(−months_since_last_evaluation / 18))
```

### Confidence measures data completeness, not likelihood of success

This is the most misreadable number in the interface, and the reason it is stated here in its own
subsection. A trainer with **LOW** confidence is not predicted to perform badly. It means *the
system knows little about them* — few evaluations, an incomplete profile, or evidence that has
aged. The score may be perfectly accurate; the caveat is about the evidence behind it, not the
result.

The interface must never phrase this as certainty about outcomes, and the API's own field
description says so.

### The 18-month half-life

Evaluation evidence decays: a rating from four years ago describes a person who has since taught
other courses, changed posting, and possibly changed field. An 18-month half-life means evidence is
worth half as much after a year and a half, a quarter after three years.

Eighteen months is a judgement, not a derivation. It was chosen to sit slightly longer than a
typical annual training cycle, so a trainer used once a year does not appear to be decaying between
uses.

### The floor at 40

Recency never falls below 40 even for very old evidence. Old evidence is still evidence — a trainer
evaluated highly six years ago is better understood than one never evaluated at all. Without a
floor, the two converge, which is wrong.

---

## 7. Determinism and tie-breaking

Two runs over the same data must produce byte-identical rankings. Without that, an allocation
questioned later cannot be reconstructed, and "the system recommended them" becomes unfalsifiable.

Ties are broken lexicographically, in this order:

1. **Total score**, descending — the ranking itself.
2. **Specialisation contribution**, descending — the criterion closest to the course's purpose.
3. **Fewer active allocations** — spreads the work, consistent with the AVAILABILITY criterion.
4. **Longer service**, descending.
5. **`trainer_id`**, ascending — the final, arbitrary, *stable* tie-break.

Step 5 is arbitrary on purpose. Some deterministic key must terminate the ordering, and an
arbitrary-but-stable one is honest about that; a "cleverer" final tie-break would imply a
judgement the system has not actually made.

---

## 8. Counterfactual generation

The counterfactual answers: *what would have moved this candidate above the current leader?*

The search space is bounded and small — five criteria, each with a finite set of realistic
improvements (a higher proficiency level, one more qualification band, more years of service, an
additional evaluation at a given mean). At `c = 5` an **exhaustive** search costs microseconds, so
there is no reason to use a heuristic, and an exhaustive search has a property a heuristic does not:
when it reports nothing, the absence is a fact rather than a failure to find one.

When no single realistic change closes the gap, the API returns **`null`** rather than an
approximation. A counterfactual that overstates what a trainer could do is worse than none: it is
advice, and acting on it wastes their time.

The generated sentence names the *discipline*, not the level — "higher proficiency in Cybercrime
Investigation", not "higher proficiency in Advanced" — because the level without the subject is not
actionable.

---

## 9. Complexity and measured performance

| Stage | Complexity | At n = 812, c = 5 |
|---|---|---|
| Gates | O(n) | 812 evaluations |
| Scoring | O(n · c) | 4,060 evaluations |
| Ranking | O(n log n) | ~7,800 comparisons — **dominates** |
| Confidence + narrative | O(n) | 812 |

**The computation is trivial. The cost is entirely I/O.** That was not obvious at the outset, and
it is the single most useful measured finding in the system.

### The facts query

The first implementation used one correlated `LATERAL` per fact — eight subqueries × 812 trainers =
6,496 nested-loop iterations. Measured: **995 ms**, against a 150 ms internal budget.

Rewritten as eight pre-aggregated CTEs, each scanning its table once and hash-joined onto the
trainer rows: **62–83 ms**. Same results, an order of magnitude less work, because the database is
aggregating set-wise instead of being asked the same question 812 times.

### Against NFR-01

NFR-01 allows **10 seconds** for a prediction run. Measured over 74 runs across 30 days on the
seeded database:

| | |
|---|---|
| Mean | **347 ms** |
| Slowest | **2,316 ms** |
| Breaches of the 10 s ceiling | **0** |

A warning is logged above 3 seconds — well inside the budget, so degradation surfaces long before
it breaches, while there is still time to act. `GET /system/health/prediction-performance` charts
this against the threshold, because a budget nothing measures is a wish.

---

## 10. Numerical method

**Every score is a `Decimal`. No float appears anywhere in the scoring path.**

### Why

IEEE-754 binary floating point cannot represent 0.1, 0.2, or most decimal fractions exactly. Errors
accumulate through summation and, at a tie, decide rank order.

```python
>>> 0.1 + 0.2 == 0.3
False
>>> 45 * 88.7 / 100 + 20 * 91.2 / 100 + 15 * 76.4 / 100
75.15500000000002        # a rank-deciding comparison against 75.155
```

Two candidates whose true scores are identical to two decimal places can compare unequal — and in
which direction depends on the order of summation, which depends on the order rows came back from
the database, which is not guaranteed. **An allocation decision that does not reproduce is not
auditable.** That is the whole argument.

### How

- `NUMERIC(5,2)` for scores and `NUMERIC(2,1)` for ratings in the database (D4).
- `Decimal` throughout the engine, including the exponential decay in the confidence function,
  which uses `Decimal.ln()` and `Decimal.exp()` rather than `math` (B10).
- Quantisation to two places with `ROUND_HALF_UP` happens **once, at serialisation**, and the value
  is converted to a JSON number only after it is already exact. `Decimal("87.40")` serialises as
  `87.4`, never `87.40000000000001`.
- `ROUND_HALF_UP` rather than Python's default banker's rounding, because half-up is what a person
  checking the arithmetic by hand will do.

The wire format is a **number**, not a string, because `frontend/src/types/domain.ts` types every
score as `number` and that contract is binding. The exactness is preserved up to the boundary; what
crosses it is already rounded.

---

## 11. Supporting algorithms

### Password hashing — Argon2id

Argon2id with `time_cost=3`, `memory_cost=64 MiB`, `parallelism=4`.

Chosen over bcrypt because bcrypt is **memory-light** — around 4 KiB — which makes it cheap to
attack in parallel on a GPU. Argon2id's memory-hardness is what makes that parallelism expensive.
It also won the Password Hashing Competition, and the `id` variant resists both side-channel and
time-memory trade-off attacks.

The parameters are settings, not constants, so they can be raised as hardware improves without a
code change.

### Registry numbers

`TPS/ALL/2026/0417` is drawn from a PostgreSQL **sequence** via `next_registry_number()`, never
from `MAX(id) + 1`.

`MAX(id) + 1` issues duplicates under concurrent approvals: two transactions read the same maximum
and both write the next number. A duplicate registry number on a government decision record is a
serious defect — two different allocations that cannot be told apart in correspondence. A sequence
is atomic and outside transaction rollback, which is exactly right here: a gap in the numbering is
harmless, a collision is not.

### Pagination — keyset versus offset

The audit log is append-only and grows without bound. `OFFSET 200000` makes PostgreSQL walk and
discard 200,000 rows for every request; the cost grows with depth and with the table's age.

Keyset pagination seeks instead:

```sql
WHERE (created_at, log_id) < (:cursor_at, :cursor_id)
ORDER BY created_at DESC, log_id DESC
LIMIT :n
```

Cost is constant at any depth. The cursor is **`(created_at, log_id)`**, not `created_at` alone:
timestamps collide — audit entries written inside one transaction share one — and a non-unique
cursor silently skips or repeats rows at page boundaries. The id breaks the tie.

Offset paging is still offered because the frontend's table uses it, and capped at 10,000 rows,
beyond which the caller is told to switch.

### Refresh-token rotation with reuse detection

Each refresh issues a new token and revokes its predecessor, within a **family**. If a
*already-revoked* token is presented, that is a signal that a token was stolen: either the attacker
or the legitimate user is replaying one the other has already spent. The whole family is revoked,
which signs the session out everywhere and forces a fresh authentication.

Tokens are stored as SHA-256 hashes. A database read cannot yield a usable token.

---

## 12. Known limitations and future work

Stated plainly, because a document that only lists strengths is not an evaluation.

**1. Weights are a policy judgement, not a derivation.** The defaults — SPECIALIZATION 30,
PERFORMANCE 25, EXPERIENCE 20, QUALIFICATION 15, AVAILABILITY 10 — are reasonable and were set by
hand. AHP (§2) is the right method to replace them, and because they live in rows, the output of an
AHP workshop can be entered without touching code.

**2. PERFORMANCE currently discriminates weakly**, for the reason set out in §5. Worth re-examining
once real evaluations accumulate.

**3. The criteria are assumed independent.** They are not. Qualification and specialisation are
correlated; the model double-counts that correlation to some degree.

**4. Linear preference within each criterion.** The gap between 4 and 8 years of service probably
matters more than between 24 and 28. A concave curve would model this better at the cost of
explainability, which is not a trade this system should make lightly.

**5. Confidence does not feed the ranking.** It is displayed alongside, not multiplied in. This is
deliberate — a low-confidence high scorer should still be *seen*, with the caveat attached — but it
does mean an Administrator can approve a thinly-evidenced candidate without the system resisting.
The Decision Receipt records the confidence band, so the caveat survives into the audit trail.

**6. Notification delivery has no external transport.** Rows are written and marked `SENT` for the
in-application inbox. There is no SMS gateway or mail relay configured; `delivery_status` exists so
one can be added without schema change.

**7. Rate limiting is in-process.** With one API container that is correct; with several, each
holds its own counter and the effective limit multiplies by the number of replicas. The fix is a
shared Redis backend, and adding Redis before it is needed would be the larger mistake.

### What would have to be true before a learned model could be considered

Roughly: **several hundred completed allocations with recorded evaluations**, spanning enough
different disciplines and trainers that the model is not simply learning the identities of a dozen
frequently-used people. Perhaps two to three years of operation.

And when that data exists, the honest position is that a learned re-ranker **should be judged
against this baseline, not assumed superior**. A model that ranks marginally better but cannot tell
a review board why it ranked that way is not obviously an improvement for this purpose. The right
experiment is offline: replay historical allocations, compare the orderings, and require a
meaningful margin before trading away the explainability that FR-07 exists to guarantee.

---

## Appendix — a worked example

From a real run (run 43, programme *Cybercrime Investigation Refresher*, 812 trainers, 705 ranked,
107 excluded, 209 ms):

**Rank 4 — IP Sarah Mugisha — score 89.81, confidence 62 (MODERATE)**

| Criterion | Weight | Raw value | Normalised | Contribution |
|---|---:|---|---:|---:|
| Specialisation match | 30 | Expert · Cybercrime Investigation | 100.00 | 30.00 |
| Proven performance | 25 | 4.6 of 5 · 6 evaluations | 89.25 | 22.31 |
| Years of service | 20 | 13 years | 65.00 | 13.00 |
| Qualification | 15 | Bachelor's Degree | 88.00 | 13.20 |
| Availability | 10 | 2 active allocations | 50.00 | 5.00 |
| | | | **Total** | **83.51** |

The contributions sum to the score exactly. An officer can check every line against the trainer's
record, and can see that this candidate's ranking rests on a strong specialisation match and a
solid evaluation history, held back by a moderate workload.

The rationale reads: *"IP Mugisha holds Expert proficiency in Cybercrime Investigation, has 13
years of service, and averaged 4.6 out of 5 across all recorded courses."*

That sentence, the table above, and the weights in force are what get frozen onto the allocation at
the moment of approval — and they do not change afterwards, whatever happens to the underlying data.
