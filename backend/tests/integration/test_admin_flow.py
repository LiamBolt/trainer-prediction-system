"""Administration, audit, dashboard, and reports (Stage 7).

The tests here concentrate on the guarantees that are easy to *claim* and easy to lose:
that a temporary password is never persisted or logged, that deactivation is immediate
rather than eventual, that the last administrator cannot be removed, that the audit log
has no write path, and that the dashboard takes the caller's role from the token rather
than from a parameter they control.
"""

from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import auth, scalar


def _suffix() -> str:
    """A short random suffix, so repeated runs do not collide on unique columns."""
    return secrets.token_hex(4)


async def _make_user(
    client: httpx.AsyncClient, sysadmin: dict[str, str], role: str, **extra: object
) -> tuple[dict[str, object], str]:
    """Create a user and return it with its temporary password.

    Args:
        client: Test client.
        sysadmin: System Administrator headers.
        role: The role to create.
        **extra: Additional body fields.

    Returns:
        The created user and its one-time password.
    """
    suffix = _suffix()
    body = {
        "username": f"test.{suffix}",
        "fullName": f"Test Person {suffix}",
        "email": f"test.{suffix}@upf.go.ug",
        "role": role,
        **extra,
    }
    response = await client.post("/users", headers=sysadmin, json=body)
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["user"], payload["temporaryPassword"]


# ----------------------------------------------------------------- FR-12


async def test_created_user_can_sign_in_and_must_change_password(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """The generated password works exactly once, and is not stored anywhere readable."""
    user, temporary = await _make_user(client, sysadmin, "TRAINING_OFFICER")
    assert user["mustChangePassword"] is True

    signed_in = await client.post(
        "/auth/login", json={"username": user["username"], "password": temporary}
    )
    assert signed_in.status_code == 200

    # The plaintext exists in the response body and nowhere else: not in the row, not
    # in the audit entry that records the creation.
    stored = await scalar(
        db, "SELECT password_hash FROM users WHERE user_id = :u", u=user["userId"]
    )
    assert temporary not in stored
    assert stored.startswith("$argon2id$")

    entry = await scalar(
        db,
        "SELECT after_json::text FROM audit_logs WHERE action = 'USER_CREATED' "
        "AND entity_id = :u",
        u=user["userId"],
    )
    assert temporary not in entry
    assert "password" not in entry.lower()


async def test_only_a_system_administrator_may_create_users(
    client: httpx.AsyncClient, admin: dict[str, str], officer: dict[str, str]
) -> None:
    """FR-12 is a System Administrator's job alone."""
    body = {
        "username": "nope.person",
        "fullName": "Nope Person",
        "email": "nope@upf.go.ug",
        "role": "TRAINING_OFFICER",
    }
    for headers in (admin, officer):
        response = await client.post("/users", headers=headers, json=body)
        assert response.status_code == 403


async def test_a_trainer_account_is_refused_without_its_profile_fields(
    client: httpx.AsyncClient, sysadmin: dict[str, str]
) -> None:
    """Every missing field is named, not just the first.

    A user filling a form wants the whole list; being told one field at a time across
    five round trips is how a five-field form takes five minutes.
    """
    suffix = _suffix()
    response = await client.post(
        "/users",
        headers=sysadmin,
        json={
            "username": f"tr.{suffix}",
            "fullName": f"Trainer {suffix}",
            "email": f"tr.{suffix}@upf.go.ug",
            "role": "TRAINER",
        },
    )
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"stationId", "directorateId", "forceNumber", "contactNumber", "rankId"}


async def test_a_trainer_account_creates_its_profile_in_the_same_transaction(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """A TRAINER user with no `trainers` row is a state that must be impossible."""
    user, _ = await _make_user(
        client,
        sysadmin,
        "TRAINER",
        stationId=1,
        directorateId=1,
        rankId=5,
        forceNumber=f"UPF/{_suffix()}",
        contactNumber="+256700000000",
        yearsExperience=6,
    )
    assert user["trainerId"] is not None
    linked = await scalar(
        db, "SELECT count(*) FROM trainers WHERE user_id = :u", u=user["userId"]
    )
    assert linked == 1


async def test_deactivation_is_immediate_not_eventual(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """An access token issued a moment ago stops working the instant the account does.

    This is why `get_current_user` re-reads the account status from the database on
    every request rather than trusting the token's claims: trusting the token would
    leave a revoked user authenticated for up to fifteen minutes.
    """
    user, temporary = await _make_user(client, sysadmin, "TRAINING_OFFICER")
    signed_in = await client.post(
        "/auth/login", json={"username": user["username"], "password": temporary}
    )
    headers = auth(signed_in.json()["token"])
    assert (await client.get("/auth/me", headers=headers)).status_code == 200

    deactivated = await client.post(f"/users/{user['userId']}/deactivate", headers=sysadmin)
    assert deactivated.status_code == 200

    refused = await client.get("/auth/me", headers=headers)
    assert refused.status_code == 403
    assert "deactivated" in refused.json()["detail"].lower()

    live = await scalar(
        db,
        "SELECT count(*) FROM refresh_tokens WHERE user_id = :u AND revoked_at IS NULL",
        u=user["userId"],
    )
    assert live == 0

    # And the correct password no longer helps.
    retry = await client.post(
        "/auth/login", json={"username": user["username"], "password": temporary}
    )
    assert retry.status_code in (401, 403)


async def test_the_last_system_administrator_cannot_be_removed(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """Locking every administrator out is only recoverable with database access.

    The seed carries several administrators, so the guard cannot fire on live data.
    The others are parked for the duration and restored afterwards.
    """
    user, temporary = await _make_user(client, sysadmin, "SYSTEM_ADMINISTRATOR")
    signed_in = await client.post(
        "/auth/login", json={"username": user["username"], "password": temporary}
    )
    headers = auth(signed_in.json()["token"])

    await db.execute(
        text(
            "UPDATE users SET account_status = 'SUSPENDED' WHERE user_id IN ("
            "  SELECT u.user_id FROM users u JOIN roles r ON r.role_id = u.role_id"
            "  WHERE r.name = 'SYSTEM_ADMINISTRATOR' AND u.account_status = 'ACTIVE'"
            "    AND u.user_id <> :keep)"
        ),
        {"keep": user["userId"]},
    )
    await db.commit()
    try:
        suspended = await client.patch(
            f"/users/{user['userId']}",
            headers=headers,
            json={"accountStatus": "SUSPENDED"},
        )
        assert suspended.status_code == 409
        assert "last active System Administrator" in suspended.json()["detail"]
    finally:
        await db.execute(
            text(
                "UPDATE users SET account_status = 'ACTIVE' WHERE account_status = 'SUSPENDED' "
                "AND role_id = (SELECT role_id FROM roles WHERE name = 'SYSTEM_ADMINISTRATOR')"
            )
        )
        await db.commit()


async def test_you_cannot_deactivate_yourself(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """Removing your own access is never the intended action."""
    me = await client.get("/auth/me", headers=sysadmin)
    user_id = me.json()["userId"]
    response = await client.post(f"/users/{user_id}/deactivate", headers=sysadmin)
    assert response.status_code == 409
    assert "your own account" in response.json()["detail"]
    _ = db


async def test_duplicate_username_is_a_conflict(
    client: httpx.AsyncClient, sysadmin: dict[str, str]
) -> None:
    """Checked in the service for a clear message; guaranteed by a UNIQUE constraint."""
    user, _ = await _make_user(client, sysadmin, "TRAINING_OFFICER")
    response = await client.post(
        "/users",
        headers=sysadmin,
        json={
            "username": user["username"],
            "fullName": "Somebody Else",
            "email": f"other.{_suffix()}@upf.go.ug",
            "role": "TRAINING_OFFICER",
        },
    )
    assert response.status_code == 409
    assert "already in use" in response.json()["detail"]


async def test_roles_carry_their_permissions(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    """The Roles screen is data-driven, so it cannot drift from the API."""
    response = await client.get("/roles", headers=admin)
    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == 4
    for role in roles:
        assert role["permissions"], f"{role['name']} has no permissions listed"
        assert role["userCount"] >= 0


# ----------------------------------------------------------------- FR-13


async def test_the_audit_log_has_no_write_path(
    client: httpx.AsyncClient, sysadmin: dict[str, str]
) -> None:
    """Not "blocked" — absent. No route exists to reach a write."""
    for method in ("post", "patch", "delete", "put"):
        response = await getattr(client, method)("/audit", headers=sysadmin)
        assert response.status_code == 405, f"{method.upper()} /audit should not exist"


async def test_audit_is_system_administrator_only(
    client: httpx.AsyncClient, admin: dict[str, str], officer: dict[str, str],
    trainer: dict[str, str],
) -> None:
    """Reading who did what is a privileged act."""
    for headers in (admin, officer, trainer):
        assert (await client.get("/audit", headers=headers)).status_code == 403


async def test_keyset_paging_does_not_repeat_or_skip(
    client: httpx.AsyncClient, sysadmin: dict[str, str]
) -> None:
    """The cursor is `(created_at, log_id)` precisely so pages do not overlap.

    A cursor on the timestamp alone silently repeats or drops rows wherever two
    entries share a timestamp — which, in an audit log written inside transactions, is
    most of them.
    """
    first = await client.get("/audit?pageSize=5", headers=sysadmin, params={"after": ""})
    assert first.status_code == 200
    page_one = first.json()
    assert page_one["hasMore"] is True

    second = await client.get(
        "/audit", headers=sysadmin, params={"pageSize": 5, "after": page_one["nextCursor"]}
    )
    assert second.status_code == 200
    page_two = second.json()

    ids_one = {row["logId"] for row in page_one["items"]}
    ids_two = {row["logId"] for row in page_two["items"]}
    assert not (ids_one & ids_two), "keyset pages overlapped"


async def test_deep_offset_paging_is_refused_with_a_reason(
    client: httpx.AsyncClient, sysadmin: dict[str, str]
) -> None:
    """A 422 that explains itself, not a 500.

    The guard lives in a `model_validator` on `PageParams`, which raises while the
    dependency is being constructed — outside FastAPI's request-validation handling.
    Without an explicit handler that surfaced as an internal error, which is the API
    reporting its own deliberate rule as a fault.
    """
    response = await client.get("/audit?page=2000&pageSize=10", headers=sysadmin)
    assert response.status_code == 422
    assert "cursor" in response.json()["detail"]


async def test_one_record_has_a_readable_history(
    client: httpx.AsyncClient, db: AsyncSession, admin: dict[str, str]
) -> None:
    """The whole point of FR-13: a decision reviewable a year later."""
    allocation_id = await scalar(
        db, "SELECT max(allocation_id) FROM allocations WHERE status = 'EVALUATED'"
    )
    if allocation_id is None:
        pytest.skip("no evaluated allocation in the database yet")

    response = await client.get(f"/audit/entity/ALLOCATION/{allocation_id}", headers=admin)
    assert response.status_code == 200
    entries = response.json()
    assert entries, "an evaluated allocation must have a history"
    assert any(entry["action"] == "ALLOCATION_APPROVED" for entry in entries)
    # Chronological, because a history out of order is not a history.
    timestamps = [entry["createdAt"] for entry in entries]
    assert timestamps == sorted(timestamps)


async def test_exporting_the_audit_log_is_itself_audited(
    client: httpx.AsyncClient, db: AsyncSession, sysadmin: dict[str, str]
) -> None:
    """Who read the log, and with what filters, is exactly what a log is for."""
    before = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'REPORT_EXPORTED'"
    )
    response = await client.get("/audit/export?action=LOGIN_SUCCESS", headers=sysadmin)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.splitlines()[0].startswith("log_id,created_at,action")

    after = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'REPORT_EXPORTED'"
    )
    assert after == before + 1


# ------------------------------------------------------------- dashboard


async def test_the_dashboard_takes_the_role_from_the_token(
    client: httpx.AsyncClient, trainer: dict[str, str]
) -> None:
    """A Trainer asking for the Administrator dashboard gets the Trainer dashboard.

    Conflict B3: the frontend sends `?role=`. Honouring it would be an authorisation
    bypass dressed as a convenience.
    """
    response = await client.get(
        "/dashboard/summary?role=SYSTEM_ADMINISTRATOR&userId=1", headers=trainer
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "TRAINER"
    # No administrator panel leaked through.
    assert "usersByRole" not in body
    assert "predictionQueue" not in body


async def test_each_role_gets_its_own_panels(
    client: httpx.AsyncClient,
    admin: dict[str, str],
    officer: dict[str, str],
    trainer: dict[str, str],
    sysadmin: dict[str, str],
) -> None:
    """Four roles, four shapes, one endpoint."""
    expected = {
        "TRAINING_ADMINISTRATOR": ("predictionQueue", admin),
        "TRAINING_OFFICER": ("myRequestsByStatus", officer),
        "TRAINER": ("profileCompleteness", trainer),
        "SYSTEM_ADMINISTRATOR": ("usersByRole", sysadmin),
    }
    for role, (panel, headers) in expected.items():
        response = await client.get("/dashboard/summary", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == role
        assert panel in body, f"{role} is missing its {panel} panel"
        # The four headline figures are on every role's dashboard.
        assert set(body["summary"]) == {
            "awaitingApproval",
            "predictionsReady",
            "allocationsThisQuarter",
            "evaluationsOutstanding",
        }


# --------------------------------------------------------------- reports


async def test_utilisation_includes_trainers_with_no_allocations(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    """The empty rows are the finding.

    A utilisation report that lists only busy people cannot show who is never used,
    which is the question the report exists to answer.
    """
    response = await client.get("/reports/utilisation", headers=admin)
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert any(row["allocations"] == 0 for row in rows)
    assert any(row["allocations"] > 0 for row in rows)
    # Ordered busiest first.
    counts = [row["allocations"] for row in rows]
    assert counts == sorted(counts, reverse=True)


async def test_reports_carry_the_filters_that_produced_them(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    """So an exported PDF can state its own provenance."""
    response = await client.get(
        "/reports/utilisation?from=2026-01-01&to=2026-12-31", headers=admin
    )
    assert response.status_code == 200
    filters = response.json()["filters"]
    assert filters["dateFrom"] == "2026-01-01"
    assert filters["dateTo"] == "2026-12-31"
    assert response.json()["generatedAt"]


async def test_reports_are_not_for_trainers(
    client: httpx.AsyncClient, trainer: dict[str, str], officer: dict[str, str]
) -> None:
    """Force-wide utilisation is management information, not self-service."""
    for path in ("/reports/utilisation", "/reports/allocation-history", "/reports/performance-trends"):
        assert (await client.get(path, headers=trainer)).status_code == 403
        assert (await client.get(path, headers=officer)).status_code == 403


async def test_report_export_streams_csv(
    client: httpx.AsyncClient, db: AsyncSession, admin: dict[str, str]
) -> None:
    """Server-side CSV, audited, with a filename."""
    before = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'REPORT_EXPORTED'"
    )
    response = await client.get("/reports/utilisation/export?format=csv", headers=admin)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("trainer_id,trainer_name")
    assert len(lines) > 100

    after = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'REPORT_EXPORTED'"
    )
    assert after == before + 1


async def test_unknown_report_type_is_a_404_that_lists_the_options(
    client: httpx.AsyncClient, admin: dict[str, str]
) -> None:
    """An error that tells you what would have worked."""
    response = await client.get("/reports/nonsense/export", headers=admin)
    assert response.status_code == 404
    assert "utilisation" in response.json()["detail"]


# --------------------------------------------------------- system health


async def test_system_health_is_system_administrator_only(
    client: httpx.AsyncClient, admin: dict[str, str], sysadmin: dict[str, str]
) -> None:
    """And reports prediction times against the NFR-01 budget."""
    for path in ("/system/health/prediction-performance", "/system/health/security"):
        assert (await client.get(path, headers=admin)).status_code == 403

    performance = await client.get(
        "/system/health/prediction-performance", headers=sysadmin
    )
    assert performance.status_code == 200
    body = performance.json()
    assert body["thresholdMs"] == 10_000
    assert body["breaches"] == sum(1 for run in body["runs"] if run["ms"] > 10_000)

    security = await client.get("/system/health/security", headers=sysadmin)
    assert security.status_code == 200
    assert set(security.json()) >= {
        "failedSignins24h",
        "lockedAccounts",
        "unauthorisedAttempts24h",
        "activeSessions",
        "deactivatedAccounts",
        "failedNotifications",
    }


# --------------------------------------------------------------- the view


async def test_scoring_facts_view_groups_evaluations_correctly(db: AsyncSession) -> None:
    """Migration 0004: the per-group counts must sum to the total.

    The previous definition evaluated `count(*) OVER (PARTITION BY ...)` inside a
    LATERAL correlated to one evaluation, so every group reported 1. Valid SQL, no
    error, plausible shape — invisible unless you check a trainer you already know has
    six evaluations in one group.
    """
    mismatches = await scalar(
        db,
        """
        SELECT count(*) FROM (
            SELECT evaluation_count,
                   (SELECT sum(value::int)
                      FROM jsonb_each_text(evaluations_by_discipline_group)) AS summed
            FROM v_trainer_scoring_facts
            WHERE evaluation_count > 0
        ) x
        WHERE summed IS DISTINCT FROM evaluation_count
        """,
    )
    assert mismatches == 0
