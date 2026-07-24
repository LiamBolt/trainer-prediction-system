"""The whole spine, end to end (§15, Stage 6).

    create → requirements → predict → approve → freeze verified immutable →
    trainer declines → promote next reuses the run → mark conducted → evaluate →
    confirm the evaluation shifts the next prediction

Each test drives the real ASGI app against the real database. That is deliberate: the
behaviours worth testing here — the transaction boundary, the `CHECK` constraints, the
`UNIQUE` on `prediction_id`, the RBAC dependencies, the frozen snapshot — are
properties of the whole assembly, and every one of them would survive a mock.
"""

from __future__ import annotations

import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import (
    audit_actions,
    auth,
    make_signable,
    scalar,
    today,
    token_for,
)


async def _programme(
    client: httpx.AsyncClient,
    officer: dict[str, str],
    admin: dict[str, str],
    *,
    title: str,
    minimum_experience: int = 3,
    offset_days: int = 200,
) -> tuple[int, dict[str, Any]]:
    """Create a programme, define requirements, and run a prediction.

    Args:
        client: Test client.
        officer: Officer headers.
        admin: Administrator headers.
        title: Programme title.
        minimum_experience: FR-05 minimum.
        offset_days: How far ahead the course sits, so tests do not collide on dates.

    Returns:
        The programme id and the prediction run.
    """
    start = today() + datetime.timedelta(days=offset_days)
    end = start + datetime.timedelta(days=10)
    created = await client.post(
        "/programmes",
        headers=officer,
        json={
            "title": title,
            "categoryId": 1,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "stationId": 1,
            "expectedParticipants": 20,
        },
    )
    assert created.status_code == 201, created.text
    programme_id = created.json()["programmeId"]

    requirements = await client.put(
        f"/programmes/{programme_id}/requirements",
        headers=officer,
        json={"requiredSpecializationAreaId": 1, "minimumExperience": minimum_experience},
    )
    assert requirements.status_code == 200, requirements.text

    run = await client.post(f"/programmes/{programme_id}/predict", headers=admin, json={})
    assert run.status_code == 201, run.text
    return programme_id, run.json()


# --------------------------------------------------------------------- FR-08


async def test_approval_freezes_the_decision(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """FR-08: approving copies the ranking into the allocation and stops there."""
    programme_id, run = await _programme(
        client, officer, admin, title="Freeze test", offset_days=201
    )
    candidate = run["predictions"][0]

    response = await client.post(
        "/allocations",
        headers=admin,
        json={"predictionId": candidate["predictionId"], "remarks": "Best available match."},
    )
    assert response.status_code == 201, response.text
    allocation = response.json()

    assert allocation["status"] == "PENDING_TRAINER"
    assert allocation["registryNumber"].startswith("TPS/ALL/")
    assert allocation["frozenScore"] == candidate["predictionScore"]
    assert allocation["frozenRankPosition"] == candidate["rankPosition"]
    assert allocation["frozenRationale"] == candidate["rationale"]
    assert allocation["frozenWeights"] == run["weights"]
    assert allocation["weightsWereSimulated"] is False

    # The Score Ledger adds up — the whole reason for choosing an additive model.
    contributions = sum(c["contribution"] for c in allocation["frozenBreakdown"])
    assert abs(contributions - allocation["frozenScore"]) < 0.01

    detail = await client.get(f"/programmes/{programme_id}", headers=admin)
    assert detail.json()["programme"]["status"] == "AWAITING_RESPONSE"

    assert "ALLOCATION_APPROVED" in await audit_actions(
        db, "ALLOCATION", allocation["allocationId"]
    )


async def test_only_an_administrator_may_approve(
    client: httpx.AsyncClient, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """BR-02: approval is a Training Administrator's act alone."""
    _, run = await _programme(client, officer, admin, title="BR-02 test", offset_days=202)
    response = await client.post(
        "/allocations",
        headers=officer,
        json={"predictionId": run["predictions"][0]["predictionId"]},
    )
    assert response.status_code == 403


async def test_a_programme_holds_one_allocation(
    client: httpx.AsyncClient, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """A course has one trainer; a second approval is a conflict, not a correction."""
    _, run = await _programme(client, officer, admin, title="One trainer", offset_days=203)
    first = await client.post(
        "/allocations", headers=admin, json={"predictionId": run["predictions"][0]["predictionId"]}
    )
    assert first.status_code == 201
    second = await client.post(
        "/allocations", headers=admin, json={"predictionId": run["predictions"][1]["predictionId"]}
    )
    assert second.status_code == 409
    assert "already has an allocation" in second.json()["detail"]


async def test_approval_rechecks_gates_against_live_data(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """A ranking is a photograph; approval checks the world as it is now.

    The candidate becomes unavailable *after* the run. Approving anyway would post an
    officer to a course they cannot attend, when the system had the information to
    prevent it.
    """
    _, run = await _programme(client, officer, admin, title="Live gate", offset_days=204)
    candidate = run["predictions"][0]
    trainer_id = candidate["trainerId"]

    previous = await scalar(
        db, "SELECT availability_status FROM trainers WHERE trainer_id = :t", t=trainer_id
    )
    await db.execute(
        text("UPDATE trainers SET availability_status = 'UNAVAILABLE' WHERE trainer_id = :t"),
        {"t": trainer_id},
    )
    await db.commit()
    try:
        blocked = await client.post(
            "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
        )
        assert blocked.status_code == 409
        assert "BR-03" in blocked.json()["detail"]
        assert "no longer be assigned" in blocked.json()["detail"]
    finally:
        await db.execute(
            text("UPDATE trainers SET availability_status = :s WHERE trainer_id = :t"),
            {"s": previous, "t": trainer_id},
        )
        await db.commit()

    allowed = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    assert allowed.status_code == 201


async def test_superseded_ranking_cannot_be_approved_from(
    client: httpx.AsyncClient, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """Approving from a regenerated ranking would record figures nobody saw."""
    programme_id, run = await _programme(
        client, officer, admin, title="Superseded", offset_days=205
    )
    stale = run["predictions"][0]["predictionId"]
    await client.post(f"/programmes/{programme_id}/predict", headers=admin, json={})

    response = await client.post("/allocations", headers=admin, json={"predictionId": stale})
    assert response.status_code == 409
    assert "regenerated" in response.json()["detail"]


async def test_changed_requirements_block_approval(
    client: httpx.AsyncClient, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """FR-05: a ranking against superseded criteria is not a basis for a decision."""
    programme_id, run = await _programme(
        client, officer, admin, title="Changed reqs", offset_days=206
    )
    await client.put(
        f"/programmes/{programme_id}/requirements",
        headers=officer,
        json={"requiredSpecializationAreaId": 1, "minimumExperience": 12},
    )
    response = await client.post(
        "/allocations",
        headers=admin,
        json={"predictionId": run["predictions"][0]["predictionId"]},
    )
    assert response.status_code == 409
    assert "requirements" in response.json()["detail"].lower()


async def test_mismatched_client_ids_are_refused(
    client: httpx.AsyncClient, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """A screen showing a different candidate from the one being approved is a defect."""
    _, run = await _programme(client, officer, admin, title="Stale screen", offset_days=207)
    response = await client.post(
        "/allocations",
        headers=admin,
        json={"predictionId": run["predictions"][0]["predictionId"], "trainerId": 999_999},
    )
    assert response.status_code == 409


# --------------------------------------------------------------------- FR-09


async def test_trainer_sees_why_they_were_selected(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """§6.3: a trainer is entitled to the reason, not merely the instruction."""
    _, run = await _programme(client, officer, admin, title="Rationale", offset_days=208)
    candidate = run["predictions"][0]
    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    assert approved.status_code == 201

    username = await make_signable(db, candidate["trainerId"])
    headers = auth(await token_for(client, username))

    mine = await client.get("/trainers/me/assignments", headers=headers)
    assert mine.status_code == 200
    pending = mine.json()["pending"]
    assert len(pending) == 1
    assert pending[0]["frozenRationale"] == candidate["rationale"]
    assert pending[0]["allocationId"] == approved.json()["allocationId"]


async def test_a_trainer_cannot_answer_for_another(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str],
    trainer: dict[str, str],
) -> None:
    """B4 layer 2: the object-level check role gating cannot express."""
    _, run = await _programme(client, officer, admin, title="Not yours", offset_days=209)
    candidate = next(
        c for c in run["predictions"] if c["trainerId"] != 1
    )
    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]

    response = await client.post(
        f"/trainers/me/assignments/{allocation_id}/accept", headers=trainer
    )
    assert response.status_code == 403


async def test_decline_requires_a_reason(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """FR-09: a refusal with no stated reason gives the Administrator nothing to act on."""
    _, run = await _programme(client, officer, admin, title="Reason required", offset_days=210)
    candidate = run["predictions"][0]
    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]
    username = await make_signable(db, candidate["trainerId"])
    headers = auth(await token_for(client, username))

    missing = await client.post(
        f"/trainers/me/assignments/{allocation_id}/decline", headers=headers, json={}
    )
    assert missing.status_code == 422

    too_short = await client.post(
        f"/trainers/me/assignments/{allocation_id}/decline",
        headers=headers,
        json={"reason": "no"},
    )
    assert too_short.status_code == 422


async def test_the_database_refuses_a_declined_row_without_a_reason(db: AsyncSession) -> None:
    """The `CHECK` behind FR-09 — a form validator is not a rule."""
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as caught:
        await db.execute(
            text(
                "UPDATE allocations SET status = 'DECLINED', decline_reason = NULL "
                "WHERE allocation_id = (SELECT min(allocation_id) FROM allocations)"
            )
        )
        await db.flush()
    assert "declined_requires_reason" in str(caught.value)
    await db.rollback()


# ----------------------------------------------------------- promote-next


async def test_promote_next_reuses_the_existing_run(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """FR-08: a decline must not trigger a new prediction.

    The offer sequence has to be explainable from one ranking. Re-running would produce
    a different order against different live data, and "why was I passed over?" would
    have no single document to answer it.
    """
    _, run = await _programme(client, officer, admin, title="Promote", offset_days=211)
    candidate = run["predictions"][0]
    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]

    username = await make_signable(db, candidate["trainerId"])
    headers = auth(await token_for(client, username))
    declined = await client.post(
        f"/trainers/me/assignments/{allocation_id}/decline",
        headers=headers,
        json={"reason": "Committed to an operation covering the whole of that fortnight."},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    assert declined.json()["declinedAt"] is not None

    promoted = await client.post(f"/allocations/{allocation_id}/promote-next", headers=admin)
    assert promoted.status_code == 201, promoted.text
    body = promoted.json()

    assert body["reusedExistingRun"] is True
    assert body["runId"] == run["runId"]
    assert body["allocation"]["frozenRankPosition"] > candidate["rankPosition"]

    # The chain of decisions is linked, not orphaned.
    superseded_by = await scalar(
        db,
        "SELECT superseded_by_allocation_id FROM allocations WHERE allocation_id = :a",
        a=allocation_id,
    )
    assert superseded_by == body["allocation"]["allocationId"]

    # And exactly one run exists for the programme — no re-prediction happened.
    runs = await scalar(
        db,
        "SELECT count(*) FROM prediction_runs WHERE programme_id = :p",
        p=run["programmeId"],
    )
    assert runs == 1

    again = await client.post(f"/allocations/{allocation_id}/promote-next", headers=admin)
    assert again.status_code == 409


async def test_promote_next_skips_candidates_who_no_longer_qualify(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """A passed-over candidate is passed over for a stated, audited reason."""
    _, run = await _programme(client, officer, admin, title="Skip check", offset_days=212)
    candidate = run["predictions"][0]
    blocked = run["predictions"][1]

    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]
    username = await make_signable(db, candidate["trainerId"])
    headers = auth(await token_for(client, username))
    await client.post(
        f"/trainers/me/assignments/{allocation_id}/decline",
        headers=headers,
        json={"reason": "Attending the senior command course over the same period."},
    )

    await db.execute(
        text("UPDATE trainers SET availability_status = 'UNAVAILABLE' WHERE trainer_id = :t"),
        {"t": blocked["trainerId"]},
    )
    await db.commit()
    try:
        promoted = await client.post(f"/allocations/{allocation_id}/promote-next", headers=admin)
        assert promoted.status_code == 201
        body = promoted.json()
        assert len(body["skipped"]) >= 1
        assert blocked["trainerName"] in body["skipped"][0]
        assert body["allocation"]["trainerId"] != blocked["trainerId"]

        skips = await scalar(
            db,
            "SELECT count(*) FROM audit_logs WHERE action = 'CANDIDATE_SKIPPED' "
            "AND entity_id = :p",
            p=blocked["predictionId"],
        )
        assert skips >= 1
    finally:
        await db.execute(
            text("UPDATE trainers SET availability_status = 'AVAILABLE' WHERE trainer_id = :t"),
            {"t": blocked["trainerId"]},
        )
        await db.commit()


# --------------------------------------------------------------------- FR-10


async def test_the_whole_spine(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """create → predict → approve → accept → conduct → evaluate, and the loop closes."""
    programme_id, run = await _programme(client, officer, admin, title="Spine", offset_days=213)
    candidate = run["predictions"][0]
    trainer_id = candidate["trainerId"]

    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]
    frozen_score = approved.json()["frozenScore"]

    username = await make_signable(db, trainer_id)
    headers = auth(await token_for(client, username))

    accepted = await client.post(
        f"/trainers/me/assignments/{allocation_id}/accept", headers=headers
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "CONFIRMED"
    assert accepted.json()["respondedAt"] is not None

    detail = await client.get(f"/programmes/{programme_id}", headers=admin)
    assert detail.json()["programme"]["status"] == "ALLOCATED"

    evaluation_date = today().isoformat()
    comments = "Delivered the syllabus in full and handled questions from the floor well."

    # FR-10 is gated on mark-conducted.
    early = await client.post(
        "/evaluations",
        headers=admin,
        json={
            "allocationId": allocation_id,
            "scoreAwarded": 4.5,
            "evaluatorComments": comments,
            "evaluationDate": evaluation_date,
        },
    )
    assert early.status_code == 409
    assert "conducted" in early.json()["detail"]

    conducted = await client.post(f"/allocations/{allocation_id}/mark-conducted", headers=admin)
    assert conducted.status_code == 200
    assert conducted.json()["status"] == "CONDUCTED"

    recorded = await client.post(
        "/evaluations",
        headers=admin,
        json={
            "allocationId": allocation_id,
            "scoreAwarded": 4.5,
            "evaluatorComments": comments,
            "evaluationDate": evaluation_date,
        },
    )
    assert recorded.status_code == 201, recorded.text
    body = recorded.json()
    assert body["evaluation"]["registryNumber"].startswith("TPS/EVL/")
    # The response states the consequence, because the consequence is real.
    assert "informs future rankings" in body["message"]

    duplicate = await client.post(
        "/evaluations",
        headers=admin,
        json={
            "allocationId": allocation_id,
            "scoreAwarded": 5.0,
            "evaluatorComments": comments,
            "evaluationDate": evaluation_date,
        },
    )
    assert duplicate.status_code == 409

    final = await client.get(f"/programmes/{programme_id}", headers=admin)
    assert final.json()["programme"]["status"] == "EVALUATED"

    # The receipt did not move while all of that happened.
    receipt = await client.get(f"/allocations/{allocation_id}", headers=admin)
    assert receipt.json()["frozenScore"] == frozen_score
    assert receipt.json()["evaluationId"] == body["evaluation"]["evaluationId"]

    actions = await audit_actions(db, "ALLOCATION", allocation_id)
    assert "ALLOCATION_APPROVED" in actions
    assert "ASSIGNMENT_ACCEPTED" in actions


async def test_an_evaluation_shifts_the_next_prediction(
    client: httpx.AsyncClient, db: AsyncSession, officer: dict[str, str], admin: dict[str, str]
) -> None:
    """The feedback loop is real: a recorded score changes the PERFORMANCE criterion.

    Asserted on the criterion's own contribution rather than on rank, because rank is
    a comparison against 700 other people and can be unmoved by a change that is
    nonetheless correctly reflected in the score.
    """
    programme_id, run = await _programme(client, officer, admin, title="Loop closes", offset_days=214)
    candidate = run["predictions"][0]
    trainer_id = candidate["trainerId"]

    def performance_of(prediction: dict[str, Any]) -> float:
        entry = next(c for c in prediction["breakdown"] if c["key"] == "PERFORMANCE")
        return float(entry["normalized"])

    before = performance_of(candidate)

    approved = await client.post(
        "/allocations", headers=admin, json={"predictionId": candidate["predictionId"]}
    )
    allocation_id = approved.json()["allocationId"]
    username = await make_signable(db, trainer_id)
    headers = auth(await token_for(client, username))
    await client.post(f"/trainers/me/assignments/{allocation_id}/accept", headers=headers)
    await client.post(f"/allocations/{allocation_id}/mark-conducted", headers=admin)

    # A deliberately poor score, so the direction of travel is unambiguous.
    await client.post(
        "/evaluations",
        headers=admin,
        json={
            "allocationId": allocation_id,
            "scoreAwarded": 1.0,
            "evaluatorComments": "Material was not prepared and the session overran badly.",
            "evaluationDate": today().isoformat(),
        },
    )

    _, second = await _programme(client, officer, admin, title="Loop again", offset_days=215)
    after_entry = next(
        (c for c in second["predictions"] if c["trainerId"] == trainer_id), None
    )
    assert after_entry is not None, "the trainer should still be ranked, merely lower"
    after = performance_of(after_entry)

    assert after < before, (
        f"PERFORMANCE should fall after a 1.0 was recorded: {before} → {after}"
    )
    _ = programme_id
