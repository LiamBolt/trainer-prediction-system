"""Tests for the guarantees the database itself is supposed to enforce.

These run against the **real** PostgreSQL database, not SQLite. SQLite has no JSONB,
different constraint semantics, no triggers of the kind used here, and no `EXCLUDE`
constraints — testing this schema against it would verify nothing that matters.

Each test attempts an illegal write and asserts it is rejected. §5.10 asks
specifically for a test proving that `UPDATE` against `audit_logs` fails; that is
:func:`test_audit_log_rejects_update`, and the rest follow the same shape because a
constraint nobody has tried to violate is a constraint nobody knows works.

Requires a migrated, seeded database. Run with::

    POSTGRES_HOST=localhost uv run pytest
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import NullPool, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from data.seed_source.generator import assert_fixtures, generate


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Yield a session on an engine of its own, always rolled back.

    A fresh engine per test rather than the shared module-level one, because
    pytest-asyncio runs each test on a new event loop and asyncpg connections are
    bound to the loop that opened them — reusing the shared engine raises
    ``RuntimeError: Event loop is closed`` from the second test onwards.

    ``NullPool`` because pooling across single-use engines buys nothing and keeps
    connections open past the loop that created them.

    Each test provokes an error, which poisons its transaction; isolating sessions
    keeps one failure from cascading into the next as a false pass.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db
        await db.rollback()
    await engine.dispose()


async def test_audit_log_rejects_update(session: AsyncSession) -> None:
    """FR-13: an audit entry cannot be edited, by any role."""
    with pytest.raises(DBAPIError) as caught:
        await session.execute(
            text(
                "UPDATE audit_logs SET action = 'LOGOUT' "
                "WHERE log_id = (SELECT min(log_id) FROM audit_logs)"
            )
        )
        await session.commit()
    assert "append-only" in str(caught.value)


async def test_audit_log_rejects_delete(session: AsyncSession) -> None:
    """FR-13: an audit entry cannot be deleted, by any role."""
    with pytest.raises(DBAPIError) as caught:
        await session.execute(
            text("DELETE FROM audit_logs WHERE log_id = (SELECT min(log_id) FROM audit_logs)")
        )
        await session.commit()
    assert "append-only" in str(caught.value)


async def test_only_one_scoring_policy_may_be_active(session: AsyncSession) -> None:
    """The partial unique index holds the single-active-policy invariant."""
    with pytest.raises(DBAPIError):
        await session.execute(
            text(
                "INSERT INTO scoring_policies (version, name, is_active) "
                "VALUES (997, 'second active', true)"
            )
        )
        await session.commit()


async def test_policy_weights_must_total_100(session: AsyncSession) -> None:
    """The deferred constraint trigger rejects a bad total at COMMIT, not before."""
    await session.execute(
        text(
            "INSERT INTO scoring_policies (version, name, is_active) VALUES (996, 'partial', false)"
        )
    )
    # Valid so far: a policy with no weights sums to 0, which is permitted (ADR-0011).
    await session.execute(
        text(
            """
            INSERT INTO scoring_policy_weights
                (policy_id, criterion_key, display_label, weight, description, sort_order)
            VALUES
                ((SELECT policy_id FROM scoring_policies WHERE version = 996),
                 'SPECIALIZATION', 'probe', 30, 'probe', 1)
            """
        )
    )
    with pytest.raises(DBAPIError) as caught:
        await session.commit()
    assert "sum to 100" in str(caught.value)


async def test_unavailability_windows_may_not_overlap(session: AsyncSession) -> None:
    """A trainer cannot be absent for two overlapping reasons at once."""
    with pytest.raises(DBAPIError):
        await session.execute(
            text(
                """
                INSERT INTO trainer_unavailability
                    (trainer_id, start_date, end_date, reason, category)
                SELECT trainer_id, start_date, end_date, 'overlap probe', 'OTHER'
                FROM trainer_unavailability ORDER BY unavailability_id LIMIT 1
                """
            )
        )
        await session.commit()


async def test_declined_allocation_requires_a_reason(session: AsyncSession) -> None:
    """FR-09: the database refuses a decline with no reason."""
    with pytest.raises(DBAPIError):
        await session.execute(
            text(
                "UPDATE allocations SET status = 'DECLINED', decline_reason = NULL, "
                "declined_at = now() WHERE allocation_id = "
                "(SELECT min(allocation_id) FROM allocations)"
            )
        )
        await session.commit()


async def test_invalid_check_value_is_rejected(session: AsyncSession) -> None:
    """A status outside the CHECK list cannot be stored."""
    with pytest.raises(DBAPIError):
        await session.execute(text("INSERT INTO audit_logs (action) VALUES ('NOT_A_REAL_ACTION')"))
        await session.commit()


async def test_registry_numbers_are_unique_and_formatted(session: AsyncSession) -> None:
    """``next_registry_number`` returns the documented shape and never repeats."""
    result = await session.execute(
        text("SELECT next_registry_number('ALL') FROM generate_series(1, 50)")
    )
    numbers = list(result.scalars().all())
    assert len(set(numbers)) == 50, "sequence produced a duplicate registry number"
    for number in numbers:
        family, year, counter = number.removeprefix("TPS/").split("/")
        assert family == "ALL"
        assert len(year) == 4 and year.isdigit()
        assert len(counter) == 4 and counter.isdigit()


async def test_unknown_registry_family_raises(session: AsyncSession) -> None:
    """An unrecognised family is an error, not a silently malformed number."""
    with pytest.raises(DBAPIError) as caught:
        await session.execute(text("SELECT next_registry_number('NOPE')"))
        await session.commit()
    assert "Unknown registry family" in str(caught.value)


def test_generator_is_deterministic() -> None:
    """The same seed produces the same dataset, run to run.

    A demo that reshuffles itself is not a demo, and a non-reproducible dataset cannot
    be reasoned about (§7.1).
    """
    first = generate(20260722)
    second = generate(20260722)

    assert [t.force_number for t in first.trainers] == [t.force_number for t in second.trainers]
    assert [u.username for u in first.users] == [u.username for u in second.users]
    assert [p.title for p in first.programmes] == [p.title for p in second.programmes]

    first_scores = [p.prediction_score for r in first.runs for p in r.predictions]
    second_scores = [p.prediction_score for r in second.runs for p in r.predictions]
    assert first_scores == second_scores


def test_a_different_seed_produces_different_data() -> None:
    """Determinism must come from the seed, not from the generator being constant."""
    baseline = generate(20260722)
    other = generate(1)
    assert [t.force_number for t in baseline.trainers] != [t.force_number for t in other.trainers]


def test_all_eight_narrative_fixtures_hold() -> None:
    """§7.4: the dataset must tell a story on first login, not present uniform noise."""
    lines = assert_fixtures(generate(20260722))
    assert len(lines) == 8
