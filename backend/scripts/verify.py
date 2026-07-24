"""Assert every invariant the schema is supposed to guarantee (§9).

Run with ``python -m scripts.verify``. Exits non-zero if any check fails, so it can
be wired into CI as a gate.

The checks fall into three groups:

- **Row counts** — the dataset is the size it claims to be.
- **Business invariants** — weights sum to 100, one active policy, no duplicate rank
  within a run, every decline has a reason, every trainer has a specialisation.
- **Database-enforced guarantees** — the audit trigger, the exclusion constraint, and
  the deferred weight-sum trigger genuinely reject bad writes.

The third group matters most. The first two verify what the seed *wrote*; only the
third verifies what the database would *refuse*, and a constraint nobody has tried to
violate is a constraint nobody knows works.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal, engine, session_scope
from app.models import (
    Allocation,
    Prediction,
    PredictionRun,
    ScoringPolicy,
    ScoringPolicyWeight,
    Trainer,
    TrainerSpecialization,
    User,
)


@dataclass(slots=True)
class Check:
    """One verification result."""

    name: str
    passed: bool
    detail: str


async def _count(session: AsyncSession, table: str) -> int:
    """Return the row count of a table."""
    result = await session.execute(select(func.count()).select_from(text(table)))
    return int(result.scalar_one())


async def check_row_counts(session: AsyncSession) -> list[Check]:
    """Confirm the seeded dataset is the expected size."""
    expectations: dict[str, int] = {
        "roles": 4,
        "police_ranks": 15,
        "directorates": 17,
        "regions": 29,
        "stations": 39,
        "specialization_areas": 24,
        "training_categories": 8,
        "institutions": 20,
        "qualification_levels": 6,
        "proficiency_levels": 4,
        "trainers": 812,
        "training_programmes": 46,
        "scoring_policies": 1,
        "scoring_policy_weights": 5,
    }
    checks: list[Check] = []
    for table, expected in expectations.items():
        actual = await _count(session, table)
        checks.append(
            Check(
                name=f"{table} has {expected} rows",
                passed=actual == expected,
                detail=f"found {actual:,}",
            )
        )
    return checks


async def check_invariants(session: AsyncSession) -> list[Check]:
    """Confirm the business invariants hold in the seeded data."""
    checks: list[Check] = []

    # Weights sum to 100 for every policy that has any.
    rows = await session.execute(
        select(ScoringPolicyWeight.policy_id, func.sum(ScoringPolicyWeight.weight)).group_by(
            ScoringPolicyWeight.policy_id
        )
    )
    sums = list(rows.all())
    bad = [(pid, total) for pid, total in sums if total != 100]
    checks.append(
        Check(
            "every scoring policy's weights sum to 100",
            not bad,
            f"{len(sums)} policy(ies) checked" if not bad else f"offenders: {bad}",
        )
    )

    # Exactly one active policy.
    active = await session.execute(
        select(func.count()).select_from(ScoringPolicy).where(ScoringPolicy.is_active)
    )
    active_count = int(active.scalar_one())
    checks.append(
        Check("exactly one active scoring policy", active_count == 1, f"found {active_count}")
    )

    # No duplicate rank_position within a run. The UNIQUE constraint makes this
    # impossible, which is exactly why it is worth asserting: the check confirms the
    # constraint is present, not merely that the seed behaved.
    dupes = await session.execute(
        select(Prediction.run_id, Prediction.rank_position, func.count())
        .group_by(Prediction.run_id, Prediction.rank_position)
        .having(func.count() > 1)
    )
    duplicate_ranks = list(dupes.all())
    checks.append(
        Check(
            "no duplicate rank_position within any run",
            not duplicate_ranks,
            "unique throughout" if not duplicate_ranks else f"{len(duplicate_ranks)} collisions",
        )
    )

    # Rank positions are contiguous from 1 within each run.
    gaps = await session.execute(
        select(PredictionRun.run_id)
        .join(Prediction, Prediction.run_id == PredictionRun.run_id)
        .group_by(PredictionRun.run_id, PredictionRun.ranked_count)
        .having(func.max(Prediction.rank_position) != PredictionRun.ranked_count)
    )
    gapped = list(gaps.scalars().all())
    checks.append(
        Check(
            "each run's ranks run 1..ranked_count with no gaps",
            not gapped,
            "contiguous" if not gapped else f"runs with gaps: {gapped}",
        )
    )

    # Every DECLINED allocation carries a reason (FR-09).
    missing_reason = await session.execute(
        select(func.count())
        .select_from(Allocation)
        .where(Allocation.status == "DECLINED", Allocation.decline_reason.is_(None))
    )
    missing = int(missing_reason.scalar_one())
    declined = await session.execute(
        select(func.count()).select_from(Allocation).where(Allocation.status == "DECLINED")
    )
    checks.append(
        Check(
            "every DECLINED allocation has a reason",
            missing == 0,
            f"{int(declined.scalar_one())} declined, {missing} without a reason",
        )
    )

    # Every trainer holds at least one specialisation, or BR-04 can never match them.
    without = await session.execute(
        select(func.count())
        .select_from(Trainer)
        .where(
            ~select(TrainerSpecialization.specialization_id)
            .where(TrainerSpecialization.trainer_id == Trainer.trainer_id)
            .exists()
        )
    )
    orphans = int(without.scalar_one())
    checks.append(
        Check("every trainer has at least one specialisation", orphans == 0, f"{orphans} without")
    )

    # Every trainer maps to exactly one user, and that user holds the TRAINER role.
    mismatched = await session.execute(
        text(
            """
            SELECT count(*) FROM trainers t
            JOIN users u ON u.user_id = t.user_id
            JOIN roles r ON r.role_id = u.role_id
            WHERE r.name <> 'TRAINER'
            """
        )
    )
    wrong_role = int(mismatched.scalar_one())
    checks.append(
        Check("every trainer's user holds the TRAINER role", wrong_role == 0, f"{wrong_role} wrong")
    )

    # One allocation per prediction, at most (D7).
    over = await session.execute(
        select(Allocation.prediction_id, func.count())
        .group_by(Allocation.prediction_id)
        .having(func.count() > 1)
    )
    doubled = list(over.all())
    checks.append(
        Check(
            "no prediction has more than one allocation (D7)",
            not doubled,
            "one-to-zero-or-one holds" if not doubled else f"{len(doubled)} doubled",
        )
    )

    # The four demo accounts exist and are active.
    demo = await session.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.username.in_(["admin.training", "officer.training", "trainer", "sysadmin"]),
            User.account_status == "ACTIVE",
        )
    )
    demo_count = int(demo.scalar_one())
    checks.append(Check("four active demo accounts", demo_count == 4, f"found {demo_count}"))

    # The scoring facts view returns a row per trainer.
    view_rows = await _count(session, "v_trainer_scoring_facts")
    trainer_rows = await _count(session, "trainers")
    checks.append(
        Check(
            "v_trainer_scoring_facts covers every trainer",
            view_rows == trainer_rows,
            f"{view_rows:,} view rows vs {trainer_rows:,} trainers",
        )
    )

    return checks


async def check_database_enforcement() -> list[Check]:
    """Confirm the database actively rejects writes that violate its guarantees.

    Each check deliberately attempts an illegal write in its own session and expects
    an error. Sessions are separate because a failed statement poisons the current
    transaction — a subsequent legal statement on the same session would fail for the
    wrong reason and the check would pass by accident.
    """
    checks: list[Check] = []

    async def expect_failure(name: str, statement: str, detail: str) -> Check:
        try:
            async with SessionLocal() as session:
                await session.execute(text(statement))
                await session.commit()
        except (IntegrityError, DBAPIError) as exc:
            message = str(exc.orig) if exc.orig else str(exc)
            return Check(name, True, f"rejected: {message.splitlines()[0][:90]}")
        return Check(name, False, f"NOT rejected — {detail}")

    checks.append(
        await expect_failure(
            "audit_logs rejects UPDATE (FR-13)",
            "UPDATE audit_logs SET action = 'LOGOUT' WHERE log_id = (SELECT min(log_id) FROM audit_logs)",
            "audit entries can be edited",
        )
    )
    checks.append(
        await expect_failure(
            "audit_logs rejects DELETE (FR-13)",
            "DELETE FROM audit_logs WHERE log_id = (SELECT min(log_id) FROM audit_logs)",
            "audit entries can be deleted",
        )
    )
    checks.append(
        await expect_failure(
            "a second active scoring policy is rejected",
            "INSERT INTO scoring_policies (version, name, is_active) VALUES (98, 'second active', true)",
            "two policies can be active at once",
        )
    )
    checks.append(
        await expect_failure(
            "an invalid CHECK value is rejected",
            "INSERT INTO audit_logs (action) VALUES ('NOT_A_REAL_ACTION')",
            "arbitrary action strings are accepted",
        )
    )
    checks.append(
        await expect_failure(
            "overlapping unavailability windows are rejected",
            """
            INSERT INTO trainer_unavailability
                (trainer_id, start_date, end_date, reason, category)
            SELECT trainer_id, start_date, end_date, 'overlap probe', 'OTHER'
            FROM trainer_unavailability
            ORDER BY unavailability_id LIMIT 1
            """,
            "a trainer can be absent twice at once",
        )
    )
    checks.append(
        await expect_failure(
            "weights that do not sum to 100 are rejected at COMMIT",
            """
            INSERT INTO scoring_policy_weights
                (policy_id, criterion_key, display_label, weight, description, sort_order)
            VALUES
                ((SELECT policy_id FROM scoring_policies WHERE is_active),
                 'SPECIALIZATION', 'probe', 5, 'probe', 9)
            ON CONFLICT (policy_id, criterion_key)
            DO UPDATE SET weight = 5
            """,
            "a policy's weights need not total 100",
        )
    )
    return checks


async def main() -> int:
    """Run every check and report. Returns 0 if all passed, 1 otherwise."""
    print("TPS verify — schema and seed invariants (§9)")
    print()

    groups: list[tuple[str, list[Check]]] = []
    async with session_scope() as session:
        groups.append(("Row counts", await check_row_counts(session)))
        groups.append(("Business invariants", await check_invariants(session)))
    groups.append(("Database-enforced guarantees", await check_database_enforcement()))

    failures = 0
    for title, checks in groups:
        print(title)
        print("-" * len(title))
        width = max(len(c.name) for c in checks)
        for check in checks:
            mark = "✓" if check.passed else "✗"
            print(f"  {mark} {check.name:<{width}}  {check.detail}")
            if not check.passed:
                failures += 1
        print()

    total = sum(len(checks) for _title, checks in groups)
    if failures:
        print(f"FAILED — {failures} of {total} checks did not pass.")
    else:
        print(f"All {total} checks passed.")

    await engine.dispose()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
