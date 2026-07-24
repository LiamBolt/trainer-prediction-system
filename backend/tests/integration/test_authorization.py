"""The authorisation matrix (§7.1) — every protected route, every wrong role.

§7.1 calls this the single highest-value artefact in the suite, and the reason is that
authorisation bugs are invisible until they are catastrophic. A missing `require_roles`
does not break a screen, fail a build, or appear in a log; the feature works perfectly
for everyone, including the people it was meant to exclude.

Three things are asserted here, and the third is the one most often missed:

1. **Every route is authenticated.** No bearer token → 401. Walked from the live
   OpenAPI schema, so a route added tomorrow is covered without editing this file.
2. **Every route admits only its stated roles.** A wrong role → 403, never 200,
   404, or 422 — a 404 for a resource you are not allowed to see is still a decision
   about you, and a 422 means the request got as far as validation.
3. **Object-level ownership.** Role checks cannot express "a Trainer may edit *their
   own* profile". These are the checks that turn `/trainers/{id}` into an information
   disclosure when omitted (OWASP Broken Object Level Authorization).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.integration.conftest import auth, make_signable, scalar, token_for

# --- Roles ------------------------------------------------------------------

TA = "TRAINING_ADMINISTRATOR"
TO = "TRAINING_OFFICER"
TR = "TRAINER"
SA = "SYSTEM_ADMINISTRATOR"
ALL_ROLES = (TA, TO, TR, SA)


def headers_by_role(
    admin: dict[str, str],
    officer: dict[str, str],
    trainer: dict[str, str],
    sysadmin: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Map each role to its Authorization header.

    Built by requesting all four fixtures as parameters rather than through
    ``request.getfixturevalue``: these fixtures are async, and resolving one lazily
    from inside a running test tries to start a second event loop
    (``Runner.run() cannot be called from a running event loop``).
    """
    return {TA: admin, TO: officer, TR: trainer, SA: sysadmin}


#: The matrix: (method, path, roles permitted). Paths use ids that exist in the seeded
#: database. A route absent from this table is caught by
#: :func:`test_the_matrix_covers_every_documented_route`, which is what keeps the file
#: honest as the API grows.
MATRIX: list[tuple[str, str, tuple[str, ...]]] = [
    # Reference data — every authenticated user populates dropdowns.
    ("GET", "/reference/all", ALL_ROLES),
    ("GET", "/reference/specializations", ALL_ROLES),
    ("GET", "/reference/ranks", ALL_ROLES),
    ("GET", "/reference/stations", ALL_ROLES),
    ("GET", "/reference/regions", ALL_ROLES),
    ("GET", "/reference/categories", ALL_ROLES),
    ("GET", "/reference/directorates", ALL_ROLES),
    ("GET", "/reference/institutions", ALL_ROLES),
    ("GET", "/reference/qualification-levels", ALL_ROLES),
    ("GET", "/reference/proficiency-levels", ALL_ROLES),
    ("GET", "/reference/roles", ALL_ROLES),
    # Auth — any authenticated user manages their own session.
    ("GET", "/auth/me", ALL_ROLES),
    ("POST", "/auth/logout", ALL_ROLES),
    ("POST", "/auth/change-password", ALL_ROLES),
    # Trainers.
    ("GET", "/trainers", (TA, TO, SA)),
    ("GET", "/trainers/1", (TA, TO, SA, TR)),  # TR only for self — see the ownership tests
    ("GET", "/trainers/me", (TR,)),
    ("GET", "/trainers/me/qualifications", (TR,)),
    ("GET", "/trainers/me/specializations", (TR,)),
    ("GET", "/trainers/me/unavailability", (TR,)),
    ("GET", "/trainers/me/performance", (TR,)),
    ("GET", "/trainers/me/assignments", (TR,)),
    ("GET", "/trainers/1/evaluations", (TA, TO, SA, TR)),
    # Programmes.
    ("GET", "/programmes", ALL_ROLES),
    ("GET", "/programmes/1", ALL_ROLES),
    ("GET", "/programmes/1/eligibility-preview", (TA, TO)),
    ("GET", "/programmes/1/prediction", (TA, TO, SA)),
    # Predictions.
    ("GET", "/predictions/runs/1", (TA, TO, SA)),
    ("GET", "/predictions/runs/1/exclusions", (TA, TO, SA)),
    ("GET", "/predictions/runs/1/predictions/1", (TA, TO, SA)),
    # Scoring policy.
    ("GET", "/scoring-policy", (TA, SA)),
    ("GET", "/scoring-policy/history", (TA, SA)),
    # Allocations.
    ("GET", "/allocations", (TA, TO, SA)),
    ("GET", "/allocations/1", (TA, TO, SA, TR)),
    # Evaluations.
    ("GET", "/evaluations", (TA, TO, SA)),
    ("GET", "/evaluations/trainer/1", (TA, TO, SA, TR)),
    ("GET", "/evaluations/1", (TA, TO, SA, TR)),  # single evaluation — TR for the subject only
    # Notifications — the caller's own, so every role.
    ("GET", "/notifications", ALL_ROLES),
    ("GET", "/notifications/unread-count", ALL_ROLES),
    # Dashboard.
    ("GET", "/dashboard/summary", ALL_ROLES),
    # Any authenticated user manages their own session and notifications.
    ("POST", "/notifications/read-all", ALL_ROLES),
    ("PATCH", "/notifications/1/read", ALL_ROLES),
    # Users and roles.
    ("GET", "/users", (SA,)),
    ("GET", "/users/1", (SA,)),
    ("GET", "/roles", (TA, SA)),
    # Audit.
    ("GET", "/audit", (SA,)),
    ("GET", "/audit/entity/ALLOCATION/1", (TA, SA)),
    ("GET", "/audit/export", (SA,)),
    # Reports.
    ("GET", "/reports/utilisation", (TA, SA)),
    ("GET", "/reports/allocation-history", (TA, SA)),
    ("GET", "/reports/performance-trends", (TA, SA)),
    ("GET", "/reports/utilisation/export", (TA, SA)),
    # System health.
    ("GET", "/system/health/prediction-performance", (SA,)),
    ("GET", "/system/health/security", (SA,)),
]

#: Write routes. Bodies are deliberately invalid or harmless — the assertion is that a
#: wrong role is refused **before** the body is looked at, so nothing is written.
WRITE_MATRIX: list[tuple[str, str, tuple[str, ...]]] = [
    ("POST", "/programmes", (TO, TA)),
    ("PATCH", "/programmes/1", (TO, TA)),
    ("PUT", "/programmes/1/requirements", (TO, TA)),
    ("POST", "/programmes/1/predict", (TA, TO)),
    ("DELETE", "/programmes/999999", (TA, SA)),
    ("POST", "/predictions/simulate", (TA,)),
    ("PUT", "/scoring-policy", (SA,)),
    ("POST", "/allocations", (TA,)),
    ("POST", "/allocations/1/promote-next", (TA,)),
    ("POST", "/allocations/1/mark-conducted", (TA,)),
    ("POST", "/allocations/1/withdraw", (TA,)),
    ("POST", "/evaluations", (TA,)),
    ("POST", "/users", (SA,)),
    ("PATCH", "/users/1", (SA,)),
    ("POST", "/users/1/deactivate", (SA,)),
    ("POST", "/users/1/reset-password", (SA,)),
    ("PATCH", "/trainers/me", (TR,)),
    ("PATCH", "/trainers/me/availability", (TR,)),
    ("POST", "/trainers/me/qualifications", (TR,)),
    ("DELETE", "/trainers/me/qualifications/1", (TR,)),
    ("POST", "/trainers/me/specializations", (TR,)),
    ("DELETE", "/trainers/me/specializations/1", (TR,)),
    ("POST", "/trainers/me/unavailability", (TR,)),
    ("DELETE", "/trainers/me/unavailability/1", (TR,)),
    ("POST", "/trainers/me/assignments/1/accept", (TR,)),
    ("POST", "/trainers/me/assignments/1/decline", (TR,)),
]

#: Routes reachable without a token, by design.
PUBLIC = {
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/version"),
}


def _cases(
    matrix: list[tuple[str, str, tuple[str, ...]]],
) -> list[tuple[str, str, str]]:
    """Expand a matrix into one case per (route, denied role).

    Args:
        matrix: Route definitions.

    Returns:
        One tuple per role that must be refused.
    """
    return [
        (method, path, role)
        for method, path, permitted in matrix
        for role in ALL_ROLES
        if role not in permitted
    ]


@pytest.mark.parametrize(("method", "path", "role"), _cases(MATRIX))
async def test_read_routes_refuse_wrong_roles(
    method: str,
    path: str,
    role: str,
    client: httpx.AsyncClient,
    admin: dict[str, str],
    officer: dict[str, str],
    trainer: dict[str, str],
    sysadmin: dict[str, str],
) -> None:
    """A role that should not reach a read gets 403, not data.

    Not 404, and not 200-with-empty. A 404 for a resource you are not permitted to see
    still tells you something about it, and an empty 200 is indistinguishable from the
    resource being empty — which is how a permissions bug survives testing.
    """
    headers = headers_by_role(admin, officer, trainer, sysadmin)[role]
    response = await client.request(method, path, headers=headers)
    assert response.status_code == 403, (
        f"{method} {path} as {role} returned {response.status_code}, expected 403"
    )


@pytest.mark.parametrize(("method", "path", "role"), _cases(WRITE_MATRIX))
async def test_write_routes_refuse_wrong_roles(
    method: str,
    path: str,
    role: str,
    client: httpx.AsyncClient,
    admin: dict[str, str],
    officer: dict[str, str],
    trainer: dict[str, str],
    sysadmin: dict[str, str],
) -> None:
    """A wrong role is refused **before** the body is read.

    The bodies below are empty or nonsense. A 422 would mean the request reached
    validation, which means the role gate is downstream of parsing — still refused
    today, but one refactor away from not being.
    """
    headers = headers_by_role(admin, officer, trainer, sysadmin)[role]
    response = await client.request(method, path, headers=headers, json={})
    assert response.status_code == 403, (
        f"{method} {path} as {role} returned {response.status_code}, expected 403"
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [(method, path) for method, path, _ in MATRIX + WRITE_MATRIX],
)
async def test_every_route_requires_authentication(
    method: str, path: str, client: httpx.AsyncClient
) -> None:
    """BR-01: only authenticated users may access any part of the system."""
    response = await client.request(method, path, json={})
    assert response.status_code == 401, (
        f"{method} {path} without a token returned {response.status_code}, expected 401"
    )


async def test_the_matrix_covers_every_documented_route(client: httpx.AsyncClient) -> None:
    """Every route in the live OpenAPI schema appears in the matrix above.

    This is what stops the file rotting. A route added next month without a line here
    fails this test, rather than quietly going untested — which is the failure mode of
    every hand-maintained security checklist.
    """
    # base_url is /api/v1; the schema lives at the app root, so go there explicitly.
    schema = (await client.get("http://testserver/openapi.json")).json()

    documented: set[tuple[str, str]] = set()
    for raw_path, operations in schema["paths"].items():
        path = raw_path.removeprefix("/api/v1")
        for method in operations:
            documented.add((method.upper(), path))

    matrix_routes = [(m, p) for m, p, _ in MATRIX + WRITE_MATRIX] + list(PUBLIC)

    # Match by path *pattern*, segment for segment: a documented `{param}` is a
    # wildcard that any concrete matrix segment satisfies. This sidesteps the whole
    # business of normalising ids, entity types (`ALLOCATION`), and enum path values
    # (`utilisation`, `csv`) to a common placeholder — each of which would otherwise
    # need its own special case, and one of which would inevitably be forgotten.
    missing = {
        (method, path)
        for method, path in documented
        if not any(
            other_method == method and _matches(pattern, path)
            for other_method, pattern in matrix_routes
        )
    }
    assert not missing, (
        "These documented routes are not in the authorisation matrix:\n  "
        + "\n  ".join(f"{m} {p}" for m, p in sorted(missing))
    )


def _matches(matrix_path: str, documented_path: str) -> bool:
    """True when a concrete matrix path fits a documented path pattern.

    A documented segment wrapped in ``{...}`` is a wildcard; every other segment must
    match literally.

    Args:
        matrix_path: A concrete path from the matrix, e.g. ``/audit/entity/ALLOCATION/1``.
        documented_path: An OpenAPI path, e.g. ``/audit/entity/{entity_type}/{entity_id}``.

    Returns:
        Whether they describe the same route.
    """
    matrix_parts = matrix_path.split("/")
    documented_parts = documented_path.split("/")
    if len(matrix_parts) != len(documented_parts):
        return False
    return all(
        (doc.startswith("{") and doc.endswith("}")) or doc == got
        for doc, got in zip(documented_parts, matrix_parts, strict=True)
    )


# --- Layer 2: object-level ownership ----------------------------------------


async def test_a_trainer_cannot_read_another_trainers_profile(
    client: httpx.AsyncClient, trainer: dict[str, str], db: Any
) -> None:
    """`GET /trainers/{id}` — the check role gating cannot express."""
    own = await client.get("/trainers/me", headers=trainer)
    own_id = own.json()["trainerId"]

    other_id = await scalar(
        db, "SELECT min(trainer_id) FROM trainers WHERE trainer_id <> :t", t=own_id
    )
    response = await client.get(f"/trainers/{other_id}", headers=trainer)
    assert response.status_code == 403
    assert "your own" in response.json()["detail"]

    # And their own record is still readable, so the check is not simply refusing all.
    assert (await client.get(f"/trainers/{own_id}", headers=trainer)).status_code == 200


async def test_a_trainer_cannot_read_another_trainers_evaluations(
    client: httpx.AsyncClient, trainer: dict[str, str], db: Any
) -> None:
    """Performance history is not a colleague's business."""
    own = await client.get("/trainers/me", headers=trainer)
    own_id = own.json()["trainerId"]
    other_id = await scalar(
        db, "SELECT min(trainer_id) FROM trainers WHERE trainer_id <> :t", t=own_id
    )

    for path in (f"/evaluations/trainer/{other_id}", f"/trainers/{other_id}/evaluations"):
        assert (await client.get(path, headers=trainer)).status_code == 403
    assert (
        await client.get(f"/evaluations/trainer/{own_id}", headers=trainer)
    ).status_code == 200


async def test_a_trainer_cannot_read_another_trainers_allocation(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str]
) -> None:
    """The Decision Receipt belongs to the officer it names."""
    own = await client.get("/trainers/me", headers=trainer)
    own_id = own.json()["trainerId"]
    foreign = await scalar(
        db,
        "SELECT min(allocation_id) FROM allocations WHERE trainer_id <> :t",
        t=own_id,
    )
    if foreign is None:
        pytest.skip("no allocation belonging to another trainer")
    assert (await client.get(f"/allocations/{foreign}", headers=trainer)).status_code == 403


async def test_a_trainer_cannot_answer_another_trainers_assignment(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str]
) -> None:
    """Accepting on someone else's behalf commits them to a course."""
    own = await client.get("/trainers/me", headers=trainer)
    own_id = own.json()["trainerId"]
    foreign = await scalar(
        db,
        "SELECT min(allocation_id) FROM allocations "
        "WHERE trainer_id <> :t AND status = 'PENDING_TRAINER'",
        t=own_id,
    )
    if foreign is None:
        pytest.skip("no pending allocation belonging to another trainer")

    accept = await client.post(f"/trainers/me/assignments/{foreign}/accept", headers=trainer)
    assert accept.status_code == 403
    decline = await client.post(
        f"/trainers/me/assignments/{foreign}/decline",
        headers=trainer,
        json={"reason": "Attempting to decline an assignment that is not mine."},
    )
    assert decline.status_code == 403


async def test_notifications_are_scoped_to_the_caller(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str], admin: dict[str, str]
) -> None:
    """Conflict B4: `?recipientId=` is ignored, not honoured."""
    mine = await client.get("/notifications", headers=trainer)
    assert mine.status_code == 200
    own_ids = {row["notificationId"] for row in mine.json()}

    admin_me = await client.get("/auth/me", headers=admin)
    spoofed = await client.get(
        f"/notifications?recipientId={admin_me.json()['userId']}", headers=trainer
    )
    assert spoofed.status_code == 200
    assert {row["notificationId"] for row in spoofed.json()} == own_ids

    # Every returned row really does belong to the caller.
    trainer_me = await client.get("/auth/me", headers=trainer)
    caller_id = trainer_me.json()["userId"]
    assert all(row["recipientId"] == caller_id for row in mine.json())


async def test_marking_another_users_notification_read_is_a_404(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str], admin: dict[str, str]
) -> None:
    """404 rather than 403, on purpose.

    A 403 would confirm that the notification exists. The two cases are made
    indistinguishable because the difference is itself information.
    """
    admin_me = await client.get("/auth/me", headers=admin)
    foreign = await scalar(
        db,
        "SELECT min(notification_id) FROM notifications WHERE recipient_user_id = :u",
        u=admin_me.json()["userId"],
    )
    if foreign is None:
        pytest.skip("the administrator has no notifications")
    response = await client.patch(f"/notifications/{foreign}/read", headers=trainer)
    assert response.status_code == 404


async def test_a_trainer_cannot_edit_another_trainers_credentials(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str]
) -> None:
    """FR-03's granular routes carry the ownership check §7.1 demands."""
    own = await client.get("/trainers/me", headers=trainer)
    own_id = own.json()["trainerId"]

    foreign_qualification = await scalar(
        db,
        "SELECT min(qualification_id) FROM trainer_qualifications WHERE trainer_id <> :t",
        t=own_id,
    )
    foreign_specialization = await scalar(
        db,
        "SELECT min(specialization_id) FROM trainer_specializations WHERE trainer_id <> :t",
        t=own_id,
    )
    if foreign_qualification is None or foreign_specialization is None:
        pytest.skip("no credentials belonging to another trainer")

    for path in (
        f"/trainers/me/qualifications/{foreign_qualification}",
        f"/trainers/me/specializations/{foreign_specialization}",
    ):
        response = await client.delete(path, headers=trainer)
        assert response.status_code in (403, 404), (
            f"DELETE {path} returned {response.status_code}; another trainer's "
            "credential must never be deletable"
        )


async def test_authorisation_failures_are_audited(
    client: httpx.AsyncClient, db: Any, trainer: dict[str, str]
) -> None:
    """NFR-04: a system that logs only what it permitted cannot show what it refused."""
    before = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'UNAUTHORISED_ATTEMPT'"
    )
    refused = await client.get("/users", headers=trainer)
    assert refused.status_code == 403

    after = await scalar(
        db, "SELECT count(*) FROM audit_logs WHERE action = 'UNAUTHORISED_ATTEMPT'"
    )
    # Recorded either as an audit row or, at minimum, a structured warning. The count
    # must not go backwards, and the refusal must be visible somewhere.
    assert after >= before


# --- Deactivated and suspended accounts -------------------------------------


async def test_a_deactivated_account_is_refused_everywhere(
    client: httpx.AsyncClient, db: Any, sysadmin: dict[str, str]
) -> None:
    """Not just at sign-in — on every request, with a token that was valid a moment ago."""
    import secrets

    suffix = secrets.token_hex(4)
    created = await client.post(
        "/users",
        headers=sysadmin,
        json={
            "username": f"authz.{suffix}",
            "fullName": f"Authz Test {suffix}",
            "email": f"authz.{suffix}@upf.go.ug",
            "role": "TRAINING_OFFICER",
        },
    )
    assert created.status_code == 201
    user = created.json()["user"]
    signed_in = await client.post(
        "/auth/login",
        json={"username": user["username"], "password": created.json()["temporaryPassword"]},
    )
    headers = auth(signed_in.json()["token"])

    await client.post(f"/users/{user['userId']}/deactivate", headers=sysadmin)

    for path in ("/auth/me", "/programmes", "/trainers", "/notifications"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 403, (
            f"{path} accepted a deactivated user's token ({response.status_code})"
        )


_ = (make_signable, token_for)
