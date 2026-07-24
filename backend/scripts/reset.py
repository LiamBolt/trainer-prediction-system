"""Wipe transactional data so real data can begin (§7.6, D10).

Run with ``python -m scripts.reset``. By default this clears every transactional
table — notifications, audit entries, evaluations, allocations, exclusions,
predictions, runs, programmes, trainer records, and non-demo users — while leaving
the reference tables, the active scoring policy, and the four demo accounts in place.

``--all`` additionally wipes the reference data and the scoring policy, returning the
database to the state immediately after ``alembic upgrade head``.

Both modes require typed confirmation. This command is the one destructive operation
in Phase 1, and it exists precisely so it can be run against a database someone cares
about; a bare ``--yes`` flag on muscle memory is how that goes wrong.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, func, select, text

from app.core.constants import DEMO_USERNAMES
from app.db.session import engine, session_scope
from app.models import User

#: Transactional tables, children first. ``CASCADE`` makes the order strictly
#: unnecessary, but stating it documents the dependency graph for a reader.
TRANSACTIONAL_TABLES: tuple[str, ...] = (
    "notifications",
    "audit_logs",
    "performance_evaluations",
    "allocations",
    "prediction_exclusions",
    "predictions",
    "prediction_runs",
    "training_programmes",
    "trainer_unavailability",
    "trainer_specializations",
    "trainer_qualifications",
    "trainers",
    "refresh_tokens",
)

#: Reference tables, cleared only under ``--all``.
REFERENCE_TABLES: tuple[str, ...] = (
    "scoring_policy_weights",
    "scoring_policies",
    "specialization_areas",
    "stations",
    "regions",
    "directorates",
    "training_categories",
    "institutions",
    "qualification_levels",
    "proficiency_levels",
    "police_ranks",
    "roles",
)

REGISTRY_SEQUENCES: tuple[str, ...] = (
    "registry_req_seq",
    "registry_all_seq",
    "registry_evl_seq",
)


async def current_counts() -> dict[str, int]:
    """Return row counts for every table about to be affected."""
    counts: dict[str, int] = {}
    async with session_scope() as session:
        for table in (*TRANSACTIONAL_TABLES, "users", *REFERENCE_TABLES):
            result = await session.execute(select(func.count()).select_from(text(table)))
            counts[table] = int(result.scalar_one())
    return counts


async def reset(wipe_reference: bool) -> None:
    """Truncate the transactional tables, and optionally the reference tables.

    ``TRUNCATE ... RESTART IDENTITY CASCADE`` rather than ``DELETE``: it is set-based
    rather than row-by-row, and it resets the identity sequences so a fresh seed
    produces ids from 1 again.

    Note that ``TRUNCATE`` is *not* blocked by the audit-immutability trigger, which
    guards row-level ``UPDATE`` and ``DELETE``. That is intentional and documented in
    ADR-0005: FR-13 protects the audit trail from users of the application, while
    whoever runs this script holds table ownership and is outside that threat model.

    Args:
        wipe_reference: Also clear reference data and the scoring policy.
    """
    async with session_scope() as session:
        tables = ", ".join(TRANSACTIONAL_TABLES)
        await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))

        if wipe_reference:
            # Users go entirely, including the demo accounts, since the roles they
            # point at are about to disappear.
            await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
            reference = ", ".join(REFERENCE_TABLES)
            await session.execute(text(f"TRUNCATE TABLE {reference} RESTART IDENTITY CASCADE"))
        else:
            await session.execute(delete(User).where(User.username.notin_(list(DEMO_USERNAMES))))

        for sequence in REGISTRY_SEQUENCES:
            await session.execute(text(f"ALTER SEQUENCE {sequence} RESTART"))


def confirm(prompt: str, expected: str) -> bool:
    """Ask for typed confirmation.

    Args:
        prompt: The question to display.
        expected: The exact word the operator must type.

    Returns:
        True if the operator typed the expected word.
    """
    print(prompt)
    try:
        answer = input(f"  Type {expected!r} to proceed: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == expected


async def main() -> int:
    """Parse arguments, confirm, and reset. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.reset",
        description="Wipe TPS transactional data (§7.6).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="wipe_all",
        help="Also wipe reference data, the scoring policy, and the demo accounts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted, then exit without changing anything.",
    )
    args = parser.parse_args()

    counts = await current_counts()
    affected = (*TRANSACTIONAL_TABLES, "users", *(REFERENCE_TABLES if args.wipe_all else ()))
    total = sum(counts[table] for table in affected)

    print("TPS reset")
    print(f"  mode: {'FULL (reference data included)' if args.wipe_all else 'transactional only'}")
    print()
    width = max(len(name) for name in affected)
    for table in affected:
        if counts[table]:
            print(f"  {table:<{width}}  {counts[table]:>8,}")
    print(f"  {'-' * width}  {'-' * 8}")
    print(f"  {'total rows':<{width}}  {total:>8,}")
    print()

    if args.dry_run:
        print("Dry run — nothing was changed.")
        await engine.dispose()
        return 0

    if args.wipe_all:
        print("This removes ALL data, including the four demo accounts and every")
        print("reference table. Afterwards the database is as it was immediately")
        print("after 'alembic upgrade head'.")
        expected = "WIPE EVERYTHING"
    else:
        print("This removes all transactional data. Reference tables, the active")
        print("scoring policy, and the four demo accounts are preserved.")
        expected = "RESET"

    if not confirm("", expected):
        print("Aborted. Nothing was changed.")
        await engine.dispose()
        return 1

    await reset(wipe_reference=args.wipe_all)
    print()
    print(f"Done. {total:,} rows removed.")
    if args.wipe_all:
        print("Run 'python -m scripts.seed' to restore the demo dataset.")
    else:
        print("Reference data and the demo accounts survive. The system is ready for")
        print("real data, or run 'python -m scripts.seed' to restore the demo dataset.")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
