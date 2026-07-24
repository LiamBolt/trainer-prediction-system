"""Async engine, session factory, and the request-scoped session dependency.

One :class:`AsyncSession` per unit of work, one transaction, committed once at the
edge. Services take a session; they never create one.
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def build_engine(echo: bool | None = None) -> AsyncEngine:
    """Create the async engine.

    Args:
        echo: Override statement logging. Defaults to the ``DB_ECHO`` setting.

    Returns:
        A configured :class:`AsyncEngine` speaking asyncpg.
    """
    settings = get_settings()

    connect_args: dict[str, object] = {}
    if settings.use_db_ssl:
        # asyncpg negotiates TLS from an SSLContext passed here. A managed database
        # (Supabase, Render) requires it; a hosted provider's `?sslmode=require` was
        # already stripped from the URL because asyncpg does not understand that keyword.
        context = ssl.create_default_context()
        if settings.db_ssl_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = context

    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo if echo is None else echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Detects connections severed by a database restart or an idle-timeout
        # reaper before handing them out, at the cost of one round-trip. Managed
        # databases close idle connections aggressively, which makes this load-bearing
        # rather than a nicety.
        pool_pre_ping=settings.db_pool_pre_ping,
        # Recycle connections before the server would drop them from under the pool.
        pool_recycle=settings.db_pool_recycle,
        connect_args=connect_args,
    )


engine: AsyncEngine = build_engine()

#: ``expire_on_commit=False`` so objects stay usable after ``commit()``. Without it,
#: every attribute access post-commit triggers a refresh — which in async
#: SQLAlchemy is not a lazy load but a ``MissingGreenlet`` exception.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session, committing on success and rolling back on error.

    Phase 2 uses this as a FastAPI ``Depends``. Teardown runs after the response, so
    the transaction spans exactly the request.

    Yields:
        An open :class:`AsyncSession`.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope for scripts and tests.

    The non-dependency form of :func:`get_session`, for the seed, reset, and verify
    scripts, which run outside any web request.

    Yields:
        An open :class:`AsyncSession`.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
