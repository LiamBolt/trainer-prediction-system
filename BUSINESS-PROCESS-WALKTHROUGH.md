# TPS — Business Process Walkthrough (Demo / Acceptance Script)

A step-by-step script for demonstrating that the **Trainer Prediction System** fulfils the
complete business process in `business_process_swimlane.png`, end to end.

Follow the **Acts** in order. Each Act tells you **which user to sign in as**, the **exact
steps** to perform, and the **evidence** to point at. Tick the boxes (`- [ ]`) as you go.

---

## 1. What this proves — the swimlane, mapped to the system

The diagram has four lanes. Every box maps to a concrete action in TPS:

| # | Swimlane step | Lane | In the system you… | Acted by |
|---|---|---|---|---|
| 1 | **Start → Login** | Training Officer | Sign in on the landing page | Training Officer |
| 2 | **Authenticated?** | Training Officer | Wrong password is rejected; correct one lets you in | Training Officer |
| 3 | **Create Training Request** | Training Officer | Training requests → *Create request* | Training Officer |
| 4 | **Define Training Requirements** | Training Officer | Set specialisation, experience, qualification | Training Officer |
| 5 | **Retrieve Trainer Records** | Prediction Engine | *(automatic)* the engine loads eligible trainers | System |
| 6 | **Evaluate Trainer Suitability** | Prediction Engine | *(automatic)* gates + weighted scoring run | System |
| 7 | **Generate Ranked Recommendations** | Prediction Engine | *(automatic)* the ranked list is produced | System |
| 8 | **Review Ranked Recommendations** | Training Administrator | Open the request's Prediction, read the ranking + exclusion ledger | Training Administrator |
| 9 | **Approve Top-Ranked Trainer?** | Training Administrator | Approve the #1 trainer (or *Select Next Ranked*) | Training Administrator |
| 10 | **Allocate Trainer** | Training Administrator | Confirm approval → a frozen Decision Receipt is written | Training Administrator |
| 11 | **Notify Trainer** | Training Administrator | *(automatic on approve)* the trainer is notified | System |
| 12 | **Receive Assignment Notification** | Trainer | Trainer sees the invitation on their dashboard | Trainer |
| 13 | **Accept Assignment?** | Trainer | Accept — or **Decline with Reason** | Trainer |
| 14 | **Confirm Assignment** | Trainer | Confirm acceptance | Trainer |
| 15 | **Update Allocation Status** | System | Status moves through the lifecycle | System |
| 16 | **Training Conducted** | Training Administrator | Mark the assignment conducted | Training Administrator |
| 17 | **Record Performance Evaluation** | Training Administrator | Evaluations → record a score + comments | Training Administrator |
| 18 | **End / performance data feeds future predictions** | — | The evaluation now influences the next run | System |

> The red **Decline → Select Next Ranked Trainer** loop is a separate branch — demonstrate it
> in the optional **Act 4B** so acceptance and decline are both shown.

---

## 2. Accounts (all use the password `Tps@2026#Demo`)

| Role in the swimlane | Username | Name |
|---|---|---|
| Training Officer | `officer.training` | ASP Joseph Okello |
| Training Administrator | `admin.training` | SSP Grace Nabirye |
| Trainer | `trainer` | IP Sarah Mugisha |
| System Administrator *(setup + audit)* | `sysadmin` | SP Denis Byaruhanga |

### Switching users
The system authorises by the **signed-in token**, so you must **fully sign out** before
switching roles (top-right avatar → **Sign out**), then sign in as the next user.

> **Tip for a smooth live demo:** open **four browser profiles / incognito windows**, one
> signed in as each role, and switch by clicking between windows instead of signing in and
> out repeatedly. Refresh a window after another role acts so it picks up new data.

---

## 3. Pre-flight checklist

- [ ] The app URL is open (your Render frontend URL, or `http://localhost:5173` if local).
- [ ] The backend is up. If it's the Render free tier, load any page once and wait ~30–60s for it to wake.
- [ ] You know the four usernames above and the password.
- [ ] Pick a **specialisation you know has trainers** (e.g. *Cybercrime Investigation* or *Command and Leadership*) so the prediction returns a healthy list.
- [ ] Have a throwaway course title ready, e.g. *"Demo Intake — Cybercrime Investigation"*.

---

## Act 1 — Training Officer: authenticate & raise the request
**Sign in as `officer.training`.** *(Swimlane: Start → Login → Authenticated? → Create Training Request → Define Training Requirements)*

**1.1 — Prove the "Authenticated?" gate (optional but persuasive)**
- [ ] On the sign-in page, enter `officer.training` with a **wrong** password → **Sign in**.
- [ ] **Evidence:** the form shows *"Incorrect username or password. N attempts remaining…"* — this is the **No** branch of *Authenticated?*.
- [ ] Now enter the correct password `Tps@2026#Demo` → **Sign in**. You land on the Officer dashboard — the **Yes** branch.

**1.2 — Create Training Request**
- [ ] Left nav → **Training requests**.
- [ ] Click **Create request** (top-right).
- [ ] Fill: **Course title** (your demo title), **Category** (pick from the dropdown), **Start date** and **End date**, **Location** (pick a station).
- [ ] Click **Create request**.
- [ ] **Evidence:** you're taken straight to the **Define requirements** screen, and the request now exists with a registry number.

**1.3 — Define Training Requirements**
- [ ] **Required specialisation:** choose the specialisation you picked in pre-flight.
- [ ] **Minimum years of experience:** e.g. `3`.
- [ ] **Minimum qualification (optional):** leave as *Any* (or pick one).
- [ ] Click **Save and run prediction**.
- [ ] **Evidence:** the requirements save **and the prediction runs immediately** — you are taken to the Prediction screen. This single action fires the whole **Prediction Engine** lane (Acts/steps 5–7).

---

## Act 2 — Prediction Engine: the automatic ranking
*(Swimlane: Retrieve Trainer Records → Evaluate Trainer Suitability → Generate Ranked Recommendations — no user action; you are just reading the result.)*

Still signed in as the Officer, on the Prediction screen:
- [ ] **Evidence — Retrieve + Evaluate:** the header reads e.g. **"N considered · M excluded · K ranked · computed in x.x s"**. "Considered" is *Retrieve Trainer Records*; "excluded" proves *Evaluate Trainer Suitability* applied the elimination gates.
- [ ] **Evidence — Generate Ranked Recommendations:** the ranked list shows trainers **in order** with a score out of 100, a score bar, and a confidence indicator.
- [ ] Expand **"… trainers were not considered"** at the bottom — the **Exclusion Ledger** groups everyone who was gated out and *why* (unavailable, missing specialisation, below minimum experience/qualification). This is the "nothing is hidden" accountability the process depends on.

> The Officer can *see* the ranking but **cannot approve** — approval belongs to the Training
> Administrator. That is the hand-off from the Prediction Engine lane to the Administrator lane.

---

## Act 3 — Training Administrator: review, approve, allocate, notify
**Sign out. Sign in as `admin.training`.** *(Swimlane: Review Ranked Recommendations → Approve Top-Ranked Trainer? → Allocate Trainer → Notify Trainer)*

**3.1 — Review Ranked Recommendations**
- [ ] Left nav → **Training requests** → open the request the Officer just created.
- [ ] Open its **Prediction** (the ranked recommendations).
- [ ] **Evidence:** you see the same ranked list. Click the **top-ranked trainer** to open their detail — score breakdown (the "Score Ledger"), the plain-English rationale, and the confidence level.

**3.2 — Approve the Top-Ranked Trainer**
- [ ] With the #1 trainer selected, click **Approve**.
- [ ] In the dialog, enter a short **remark/justification** and confirm.
- [ ] **Evidence — Allocate Trainer:** an allocation is created with a **registry number**, and its scores are **frozen** into a Decision Receipt (the ranking at the moment of approval is preserved even if data later changes).
- [ ] **Evidence — Notify Trainer:** you'll see a confirmation that *"the trainer has been notified."*
- [ ] Left nav → **Allocations** → the new allocation appears with a status like *Awaiting trainer*.

> **Approve Top-Ranked Trainer? = No path:** if you would rather not approve #1, you would
> instead pick the next-ranked candidate — that is the **Select Next Ranked Trainer** loop.
> Demonstrate it in **Act 4B**.

---

## Act 4 — Trainer: receive & accept
**Sign out. Sign in as `trainer`.** *(Swimlane: Receive Assignment Notification → Accept Assignment? → Confirm Assignment)*

**4.1 — Receive Assignment Notification**
- [ ] On the Trainer dashboard, find **Pending assignment invitations** (and note the bell icon shows a new notification).
- [ ] **Evidence:** the invitation names the course and shows the "Live gate" summary (your specialisation, years of service, mean evaluation) — this is *Receive Assignment Notification*.
- [ ] Click **Respond** (this takes you to **My assignments**).

**4.2 — Accept Assignment → Confirm**
- [ ] In **My assignments**, open the pending invitation.
- [ ] Click **Accept** and confirm.
- [ ] **Evidence:** the assignment status changes to **Accepted / Confirmed** — this is *Accept Assignment? → Yes → Confirm Assignment*, and the allocation status updates.

---

## Act 5 — Training Administrator: conduct & evaluate (close the loop)
**Sign out. Sign in as `admin.training`.** *(Swimlane: Update Allocation Status → Training Conducted → Record Performance Evaluation → End)*

**5.1 — Training Conducted**
- [ ] Left nav → **Allocations** → open the accepted allocation.
- [ ] Mark it **Conducted** (the action that records the training as delivered).
- [ ] **Evidence:** the allocation status moves to *Conducted* — this is *Update Allocation Status → Training Conducted*.

**5.2 — Record Performance Evaluation**
- [ ] Left nav → **Evaluations** → start a **Record evaluation** for that conducted assignment.
- [ ] Enter a **score (out of 5)** and **evaluator comments**, set the evaluation date, and save.
- [ ] **Evidence:** the evaluation is recorded against the trainer — this is *Record Performance Evaluation → End*.

**5.3 — "Performance data feeds future predictions" (the dashed loop)**
- [ ] Sign in as `trainer` again and open **My performance** → your new score appears in the history and the trend.
- [ ] *(Optional strong proof)* As the Officer, run a **new** prediction for a course in that trainer's specialisation → their **Proven performance** criterion now reflects the score you just recorded. This is the dashed *performance data feeds future predictions* arrow, closing the cycle.

---

## Act 4B — (Optional) The Decline branch: "Decline with Reason → Select Next Ranked Trainer"
Run this on a **second** request to show the full diagram, including the red loop.

1. As **Officer**, create a second request + requirements and run the prediction (repeat Acts 1–2).
2. As **Administrator**, approve the **top-ranked** trainer (Act 3).
3. As **Trainer**, open **My assignments** → **Decline** and enter a **reason** → confirm.
   - **Evidence:** *Accept Assignment? → No → Decline with Reason.*
4. As **Administrator**, open that allocation → **Promote next candidate** (reuses the same ranking — no re-run).
   - **Evidence:** *Select Next Ranked Trainer* — the next-ranked trainer is allocated and notified.
5. Sign in as that **next trainer** and **Accept** to complete the branch.

---

## Act 0 — (Optional) System Administrator: governance behind the process
Run this **before Act 1** to show the foundations, or **after Act 5** to show the audit trail.
**Sign in as `sysadmin`.**

- **Accounts exist / can be provisioned (supports every "Login"):** **Users and roles** → search the directory. Optionally **Create user** — the system shows a **one-time temporary password** to hand over (no email is sent by design). *Forgot password / locked out?* use **Reset password / unlock**.
- **The weighting the engine uses (supports "Evaluate Trainer Suitability"):** **Scoring policy** → the force-wide criterion weights that drive every prediction's score.
- **Everything is recorded (supports the whole process):** **Audit log** → after running Acts 1–5, filter the log and show the trail: sign-ins, request created, requirements defined, prediction generated, allocation approved, assignment accepted/declined, evaluation recorded. This is the "every trainer is accountable" guarantee, evidenced.

---

## 4. Completion checklist — "the system fulfilled the business process"

- [ ] **Login + Authenticated?** — wrong password rejected, correct one accepted (Act 1.1)
- [ ] **Create Training Request** (Act 1.2)
- [ ] **Define Training Requirements** (Act 1.3)
- [ ] **Retrieve / Evaluate / Generate** — ranked list + exclusion ledger produced automatically (Act 2)
- [ ] **Review Ranked Recommendations** (Act 3.1)
- [ ] **Approve Top-Ranked Trainer? → Allocate Trainer** — frozen Decision Receipt (Act 3.2)
- [ ] **Notify Trainer** — trainer notified (Act 3.2)
- [ ] **Receive Assignment Notification** (Act 4.1)
- [ ] **Accept Assignment? → Confirm Assignment** (Act 4.2)
- [ ] **Decline with Reason → Select Next Ranked Trainer** (Act 4B)
- [ ] **Update Allocation Status → Training Conducted** (Act 5.1)
- [ ] **Record Performance Evaluation → End** (Act 5.2)
- [ ] **Performance data feeds future predictions** (Act 5.3)
- [ ] *(Optional)* Governance + audit trail shown (Act 0)

When every box above is ticked, you have demonstrated the entire swimlane, in order, across all
four actors — the system has fulfilled the business process end to end.
