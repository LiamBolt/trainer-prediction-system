"""Shared fixtures for the integration tests.

These run against the **real** PostgreSQL database over the **real** ASGI app. Nothing
here is mocked: the point of an integration test in this system is to prove that the
transaction boundary, the database constraints, the RBAC dependencies, and the
business rules hold together when they are wired up, and a mock of any one of them
would remove exactly the thing being tested.

Requires a migrated, seeded database::

    POSTGRES_HOST=localhost uv run pytest tests/integration
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.constants import DEMO_PASSWORD
from app.main import create_app


@pytest.fixture(autouse=True)
def _disable_rate_limiting() -> Iterator[None]:
    """Turn the rate limiter off for the suite, and on again afterwards.

    Every test signs in up to four times to obtain role headers, and the suite makes
    several hundred sign-ins in well under a minute — far past the 10/minute production
    limit, all from 127.0.0.1. Leaving it on would make unrelated tests fail with 429s
    that look like authorisation bugs.

    Turning it off here rather than lowering it in configuration keeps the *production*
    limit exactly as shipped. `test_rate_limiting.py` re-enables it deliberately and
    proves it fires.
    """
    from app.core.rate_limit import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
async def _dispose_app_engine() -> AsyncIterator[None]:
    """Dispose the application's shared engine after every test.

    ``app.db.session.engine`` is created at import time and its pooled asyncpg
    connections are bound to whichever event loop first used them. pytest-asyncio gives
    each test a fresh loop, so from the second test onwards a pooled connection would
    be handed to a loop that did not open it — surfacing as
    ``got Future attached to a different loop``, several frames deep inside asyncpg and
    entirely unrelated to whatever the test was actually checking.

    Disposing between tests costs a handful of connection setups and removes a whole
    class of confusing failure.
    """
    yield
    from app.db.session import engine

    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield a client speaking to the real app in-process.

    ``ASGITransport`` rather than a live server: the same routing, middleware,
    dependency resolution and exception handling run, without a port.
    """
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver/api/v1"
    ) as http:
        yield http


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Yield a session for arranging fixtures and asserting on stored state.

    A fresh engine per test — pytest-asyncio gives each test a new event loop, and
    asyncpg connections are bound to the loop that opened them.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


async def token_for(client: httpx.AsyncClient, username: str) -> str:
    """Sign in and return an access token.

    Args:
        client: The test client.
        username: One of the four demo accounts.

    Returns:
        A bearer token.
    """
    response = await client.post(
        "/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["token"])


def auth(token: str) -> dict[str, str]:
    """Build an Authorization header."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(client: httpx.AsyncClient) -> dict[str, str]:
    """Headers for the Training Administrator."""
    return auth(await token_for(client, "admin.training"))


@pytest.fixture
async def officer(client: httpx.AsyncClient) -> dict[str, str]:
    """Headers for the Training Officer."""
    return auth(await token_for(client, "officer.training"))


@pytest.fixture
async def sysadmin(client: httpx.AsyncClient) -> dict[str, str]:
    """Headers for the System Administrator."""
    return auth(await token_for(client, "sysadmin"))


@pytest.fixture
async def trainer(client: httpx.AsyncClient) -> dict[str, str]:
    """Headers for the demo Trainer."""
    return auth(await token_for(client, "trainer"))


async def make_signable(db: AsyncSession, trainer_id: int) -> str:
    """Give a bulk-seeded trainer the demo account's password hash.

    The seed deliberately leaves the 850 bulk trainers with an unusable hash — they are
    data, not credentials. A test that needs to *act as* one of them borrows the demo
    hash for the duration. This changes no application behaviour; it only makes an
    account reachable through the same login path every other account uses.

    Args:
        db: A session.
        trainer_id: Whose account to make signable.

    Returns:
        The username to sign in with.
    """
    await db.execute(
        text(
            "UPDATE users SET password_hash = "
            "(SELECT password_hash FROM users WHERE username = 'trainer') "
            "WHERE user_id = (SELECT user_id FROM trainers WHERE trainer_id = :tid)"
        ),
        {"tid": trainer_id},
    )
    await db.commit()
    result = await db.execute(
        text(
            "SELECT u.username FROM users u JOIN trainers t ON t.user_id = u.user_id "
            "WHERE t.trainer_id = :tid"
        ),
        {"tid": trainer_id},
    )
    return str(result.scalar_one())


async def audit_actions(db: AsyncSession, entity_type: str, entity_id: int) -> list[str]:
    """Return the audit actions recorded against one entity, oldest first.

    Args:
        db: A session.
        entity_type: e.g. ``"ALLOCATION"``.
        entity_id: Its primary key.

    Returns:
        The action names.
    """
    result = await db.execute(
        text(
            "SELECT action FROM audit_logs WHERE entity_type = :et AND entity_id = :eid "
            "ORDER BY log_id"
        ),
        {"et": entity_type, "eid": entity_id},
    )
    return [str(row[0]) for row in result.all()]


def today() -> datetime.date:
    """Today's date, timezone-aware at the source.

    ``date.today()`` reads the machine's local zone implicitly, which is exactly the
    ambiguity §14.1 forbids — and ruff's DTZ011 refuses it. Tests obey the same rule as
    the application code.
    """
    return datetime.datetime.now(datetime.UTC).date()


async def scalar(db: AsyncSession, query: str, **params: Any) -> Any:
    """Run a scalar query, for asserting on stored state."""
    result = await db.execute(text(query), params)
    return result.scalar_one_or_none()
