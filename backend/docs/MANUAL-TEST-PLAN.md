# Manual test plan

A functional walk-through you can run yourself to confirm the whole system works — every
SRS feature, in the order the workflow actually happens. Works against **local**
(`http://localhost:8001`) or **Render** (`https://<service>.onrender.com`); set `API`
once and the rest follows.

The automated suite (355 tests) already proves this at the code level. This document is
for *your* confidence — a person clicking through, or curling, and seeing it behave.

```bash
API=http://localhost:8001          # or your Render URL
```

A tiny helper so the examples read cleanly:

```bash
login () { curl -s -X POST $API/api/v1/auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"$1\",\"password\":\"Tps@2026#Demo\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])"; }
TA=$(login admin.training); TO=$(login officer.training); TR=$(login trainer); SA=$(login sysadmin)
auth () { curl -s -H "Authorization: Bearer $1" "${@:2}"; }
```

Each section states **what it proves** and the **expected result**. Tick as you go.

---

## 0. The system is up

```bash
curl -s $API/health/ready        # → "status":"ready", database "healthy":true
curl -s $API/version             # → version, commit, environment
```

- [ ] `ready`, database healthy
- [ ] On Render: `environment` is `production`

---

## 1. Authentication and lockout (FR-01, BR-01)

```bash
# Right password → a token and the user's role
curl -s -X POST $API/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin.training","password":"Tps@2026#Demo"}' | python3 -m json.tool

# Wrong password five times → the account locks (423) on the 6th within the window
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "%{http_code} " -X POST $API/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"officer.training","password":"wrong"}'
done; echo
```

- [ ] Correct sign-in returns `token`, `refreshToken`, and the `user` with their role
- [ ] Repeated failures return `401 401 401 401 401 423` (locked for 15 min)
- [ ] No endpoint works without a token: `curl -s -o /dev/null -w "%{http_code}\n" $API/api/v1/trainers` → `401`

> The lockout is real — if you lock `officer.training`, wait 15 minutes or reset it:
> `POSTGRES_HOST=localhost uv run python -c "import asyncio…"` — simplest is to just use a
> different account for the rest, or re-seed.

---

## 2. Reference data and the trainer directory (FR-03, §6.3)

```bash
auth $TA "$API/api/v1/reference/all" | python3 -c "import sys,json;d=json.load(sys.stdin);print({k:len(v) for k,v in d.items()})"
auth $TA "$API/api/v1/trainers?pageSize=3" | python3 -m json.tool | head -30
auth $TA "$API/api/v1/trainers?search=mugisha&pageSize=3" | python3 -c "import sys,json;print([t['fullName'] for t in json.load(sys.stdin)['items']])"
```

- [ ] `/reference/all` returns every dropdown list in one response
- [ ] The directory is paginated (`items`, `total`, `page`, `pageSize`, `totalPages`)
- [ ] Fuzzy search finds trainers by partial name

---

## 3. Raise a request and set requirements (FR-04, FR-05)

```bash
# Create a programme as the Officer
PID=$(auth $TO -X POST "$API/api/v1/programmes" -H 'Content-Type: application/json' \
  -d '{"title":"Manual Test — Cybercrime Refresher","categoryId":1,"startDate":"2027-02-01","endDate":"2027-02-12","stationId":1,"expectedParticipants":25}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['programmeId'])")
echo "programme $PID"

# Predicting now is refused — no requirements yet (FR-05)
auth $TA -o /dev/null -w "predict-too-early: %{http_code}\n" -X POST "$API/api/v1/programmes/$PID/predict" -H 'Content-Type: application/json' -d '{}'

# Preview eligibility, then set requirements
auth $TO "$API/api/v1/programmes/$PID/eligibility-preview?requiredSpecializationAreaId=1&minimumExperience=3" | python3 -c "import sys,json;print(json.load(sys.stdin)['message'])"
auth $TO -X PUT "$API/api/v1/programmes/$PID/requirements" -H 'Content-Type: application/json' \
  -d '{"requiredSpecializationAreaId":1,"minimumExperience":3}' | python3 -c "import sys,json;print('status:',json.load(sys.stdin)['status'])"
```

- [ ] Create returns `201`, a registry number `TPS/REQ/2026/…`, status `DRAFT`
- [ ] Predicting before requirements → `409` citing FR-05
- [ ] Eligibility preview returns a count sentence (*"N of 812 trainers meet these criteria"*)
- [ ] Setting requirements moves the status to `REQUIREMENTS_SET`

---

## 4. Generate a ranking and read the Score Ledger (FR-06, FR-07, BR-05)

```bash
RUN=$(auth $TA -X POST "$API/api/v1/programmes/$PID/predict" -H 'Content-Type: application/json' -d '{}')
echo "$RUN" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('run',d['runId'],'ranked',d['rankedCount'],'excluded',d['excludedCount'],'in',d['elapsedMs'],'ms')
top=d['predictions'][0]
print('#1',top['trainerRank'],top['trainerName'],'score',top['predictionScore'],'confidence',top['confidenceLevel'],top['confidenceBand'])
print('ledger sums to', round(sum(c['contribution'] for c in top['breakdown']),2),'= score',top['predictionScore'])
"
```

- [ ] `201` with `rankedCount` + `excludedCount` = pool, elapsed well under 10 000 ms
- [ ] **The breakdown contributions sum exactly to the score** (the whole point of the model)
- [ ] Results are ordered by rank (no way to re-sort — BR-05)
- [ ] Some candidates show `LOW` confidence — that is *data completeness*, not a low score

---

## 5. The Exclusion Ledger — "why isn't so-and-so on the list?" (BR-03, BR-04)

```bash
RUNID=$(echo "$RUN" | python3 -c "import sys,json;print(json.load(sys.stdin)['runId'])")
auth $TA "$API/api/v1/predictions/runs/$RUNID/exclusions" | python3 -c "
import sys,json
for g in json.load(sys.stdin): print(f\"{g['count']:4} {g['reason']:28} [{g['businessRule']}]  e.g. {g['trainers'][0]['reasonDetail']}\")"
```

- [ ] Each group has a count, a rule citation (BR-03/BR-04/FR-05), and a plain-English reason
- [ ] Excluded trainers are **absent** from the ranking, not listed at the bottom

---

## 6. Weight Studio — simulate without persisting (FR-07, §6.5)

```bash
auth $TA -X POST "$API/api/v1/predictions/simulate" -H 'Content-Type: application/json' \
  -d "{\"programmeId\":$PID,\"weights\":{\"SPECIALIZATION\":45,\"PERFORMANCE\":20,\"EXPERIENCE\":15,\"QUALIFICATION\":15,\"AVAILABILITY\":5}}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('persisted:',d['persisted'],'| rank moves:',len([x for x in d['rankDeltas'] if x['movement']]))"

# Weights that don't total 100 are refused
auth $TA -o /dev/null -w "bad-weights: %{http_code}\n" -X POST "$API/api/v1/predictions/simulate" -H 'Content-Type: application/json' \
  -d "{\"programmeId\":$PID,\"weights\":{\"SPECIALIZATION\":50,\"PERFORMANCE\":20,\"EXPERIENCE\":15,\"QUALIFICATION\":15,\"AVAILABILITY\":5}}"

# An Officer cannot simulate (TA only)
auth $TO -o /dev/null -w "officer-simulate: %{http_code}\n" -X POST "$API/api/v1/predictions/simulate" -H 'Content-Type: application/json' -d "{\"programmeId\":$PID,\"weights\":{\"SPECIALIZATION\":45,\"PERFORMANCE\":20,\"EXPERIENCE\":15,\"QUALIFICATION\":15,\"AVAILABILITY\":5}}"
```

- [ ] Simulation returns `persisted: false` and a list of rank movements
- [ ] Weights not summing to 100 → `422`
- [ ] Officer simulating → `403`

---

## 7. Approve — the decision (FR-08, BR-02, BR-06)

```bash
PRED=$(echo "$RUN" | python3 -c "import sys,json;print(json.load(sys.stdin)['predictions'][0]['predictionId'])")

# An Officer cannot approve (BR-02)
auth $TO -o /dev/null -w "officer-approve: %{http_code}\n" -X POST "$API/api/v1/allocations" -H 'Content-Type: application/json' -d "{\"predictionId\":$PRED}"

# The Administrator approves — the Decision Receipt is frozen
ALLOC=$(auth $TA -X POST "$API/api/v1/allocations" -H 'Content-Type: application/json' \
  -d "{\"predictionId\":$PRED,\"remarks\":\"Manual test approval.\"}")
echo "$ALLOC" | python3 -c "
import sys,json; a=json.load(sys.stdin)
print('registry',a['registryNumber'],'status',a['status'])
print('frozen score',a['frozenScore'],'rank',a['frozenRankPosition'],'weightsWereSimulated',a['weightsWereSimulated'])
print('approved by',a['approvedByRank'],a['approvedByName'])
print('ledger sums to',round(sum(c['contribution'] for c in a['frozenBreakdown']),2))
"
AID=$(echo "$ALLOC" | python3 -c "import sys,json;print(json.load(sys.stdin)['allocationId'])")
```

- [ ] Officer approving → `403` (only a Training Administrator may — BR-02)
- [ ] Approval returns `201`, a `TPS/ALL/…` registry number, status `PENDING_TRAINER`
- [ ] The frozen breakdown still sums to the frozen score
- [ ] A second approval on the same programme → `409` ("already has an allocation")

---

## 8. The trainer responds (FR-09)

This needs to act *as the assigned trainer*. If the approved trainer is the demo
`trainer` account you can use `$TR`; otherwise this is easier to do in the frontend, or
skip to section 9 using a programme where you approved the demo trainer. To force the
demo trainer, approve their prediction specifically (find their `trainerId` = 1 in the
run's predictions).

```bash
# As the assigned trainer — see the invitation, with the reason you were chosen
auth $TR "$API/api/v1/trainers/me/assignments" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('pending',len(d['pending']),'upcoming',len(d['upcoming']),'past',len(d['past']))
if d['pending']: print('why me:', d['pending'][0]['frozenRationale'][:100])"

# Decline needs a reason (422 without one)
# auth $TR -o /dev/null -w "%{http_code}\n" -X POST "$API/api/v1/trainers/me/assignments/$AID/decline" -H 'Content-Type: application/json' -d '{}'
# auth $TR -X POST "$API/api/v1/trainers/me/assignments/$AID/accept"
```

- [ ] The trainer's pending list carries the **rationale** (they see *why* they were picked)
- [ ] Declining with no reason → `422`; with a reason → `200`, status `DECLINED`
- [ ] Accepting → `200`, status `CONFIRMED`, programme → `ALLOCATED`
- [ ] A different trainer cannot accept/decline this assignment → `403`

---

## 9. Promote-next, conduct, evaluate (FR-08, FR-10)

```bash
# After a decline: the next candidate comes from the SAME run (no re-prediction)
# auth $TA -X POST "$API/api/v1/allocations/$AID/promote-next" | python3 -c "import sys,json;d=json.load(sys.stdin);print('reusedExistingRun:',d['reusedExistingRun'],'skipped:',len(d['skipped']))"

# Mark conducted, then evaluate (evaluation is refused before CONDUCTED)
auth $TA -X POST "$API/api/v1/allocations/$AID/mark-conducted" | python3 -c "import sys,json;print('status:',json.load(sys.stdin)['status'])"
auth $TA -X POST "$API/api/v1/evaluations" -H 'Content-Type: application/json' \
  -d "{\"allocationId\":$AID,\"scoreAwarded\":4.5,\"evaluatorComments\":\"Delivered the material clearly and handled questions well.\",\"evaluationDate\":\"2027-02-13\"}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['evaluation']['registryNumber'],'—',d['message'])"
```

- [ ] `promote-next` returns `reusedExistingRun: true` (a decline never re-runs the prediction)
- [ ] Evaluating before `mark-conducted` → `409`
- [ ] `mark-conducted` → status `CONDUCTED`; then evaluation → `201`
- [ ] The response message states the consequence: *"…now informs future rankings for …"*
- [ ] A second evaluation on the same allocation → `409`

---

## 10. The decision is reviewable a year later (FR-13)

```bash
auth $SA "$API/api/v1/audit/entity/ALLOCATION/$AID" | python3 -c "
import sys,json
for e in json.load(sys.stdin): print(e['createdAt'][:19], e['action'], '—', (e['detail'] or '')[:60])"
```

- [ ] The allocation's whole history is there in order: approved → (declined/promoted) → conducted → evaluated
- [ ] `GET /audit` as anyone but a System Administrator → `403`
- [ ] `POST/PATCH/DELETE /audit` → `405` (the audit log has no write path)

---

## 11. Reports and the utilisation check (FR-11)

```bash
auth $TA "$API/api/v1/reports/utilisation" | python3 -c "
import sys,json; d=json.load(sys.stdin)
busy=[r for r in d['rows'] if r['allocations']>0][:3]; none=[r for r in d['rows'] if r['allocations']==0]
for r in busy: print(f\"{r['rank']:4} {r['trainerName']:22} {r['allocations']} allocations\")
print(f'… and {len(none)} trainers with none')"

auth $TA "$API/api/v1/reports/utilisation/export?format=csv" | head -3
```

- [ ] Utilisation lists the busiest trainers **and** those with zero (the finding, not an omission)
- [ ] CSV export streams with a header row
- [ ] Reports as a Trainer or Officer → `403`

---

## 12. Administration and system health (FR-12, §6.14)

```bash
# Roles carry their permission matrix (data-driven)
auth $SA "$API/api/v1/roles" | python3 -c "import sys,json;print([(r['displayName'],r['userCount']) for r in json.load(sys.stdin)])"

# Create a user — password returned once, never stored
auth $SA -X POST "$API/api/v1/users" -H 'Content-Type: application/json' \
  -d '{"username":"manual.check","fullName":"Manual Check","email":"manual.check@upf.go.ug","role":"TRAINING_OFFICER"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('created',d['user']['username'],'temp pw len',len(d['temporaryPassword']),'mustChange',d['user']['mustChangePassword'])"

# System health
auth $SA "$API/api/v1/system/health/prediction-performance" | python3 -c "import sys,json;d=json.load(sys.stdin);print('runs',len(d['runs']),'mean',d['meanMs'],'ms threshold',d['thresholdMs'],'breaches',d['breaches'])"
auth $SA "$API/api/v1/system/health/security" | python3 -m json.tool
```

- [ ] Roles endpoint returns the four roles with permission lists and user counts
- [ ] Creating a user returns a **one-time** temporary password with `mustChangePassword: true`
- [ ] Creating a user as anyone but a System Administrator → `403`
- [ ] Prediction-performance shows run times against the 10 000 ms threshold, 0 breaches
- [ ] Security health shows failed sign-ins, locked accounts, active sessions

---

## 13. The dashboard adapts to who is asking (§6.13)

```bash
for role in TA TO TR SA; do
  tok=$(eval echo \$$role)
  echo -n "$role → "
  auth $tok "$API/api/v1/dashboard/summary" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['role'],'panels:',sorted(k for k,v in d.items() if v is not None and k not in('role','summary')))"
done

# A Trainer asking for the Administrator dashboard still gets the Trainer dashboard
auth $TR "$API/api/v1/dashboard/summary?role=SYSTEM_ADMINISTRATOR" | python3 -c "import sys,json;print('trainer asked for SA, got:',json.load(sys.stdin)['role'])"
```

- [ ] Each role gets a different set of panels
- [ ] `?role=` is ignored — the role comes from the token, not the URL

---

## Cleanup (local only)

The manual test created one programme, one allocation, one evaluation, and one user. To
remove them and start fresh:

```bash
POSTGRES_HOST=localhost uv run python -m scripts.reset --all   # wipes transactional data
POSTGRES_HOST=localhost uv run python -m scripts.seed          # reload the demo dataset
```

On Supabase, the same commands with `DATABASE_URL=…` set. Do **not** run `reset` against a
database you care about without meaning to — it asks for typed confirmation for exactly
that reason.

---

## What "all green" looks like

Every box ticked means: authentication and lockout, the full FR-04 → FR-10 decision
spine, the frozen Decision Receipt, the Exclusion Ledger, the Weight Studio, RBAC in both
layers, the append-only audit trail, reports, user administration, and the role-adaptive
dashboard are all working — against whichever database `API` points at.
