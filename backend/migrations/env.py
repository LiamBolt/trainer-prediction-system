"""Alembic environment — async template.

Two things here are load-bearing:

1. ``from app.models import Base`` imports **every** model module (that is what
   ``app/models/__init__.py`` is for). Without it, ``target_metadata`` would be
   partially populated and autogenerate would emit a migration dropping the tables it
   could not see.
2. ``compare_type`` and ``compare_server_default`` are enabled so that a widened
   ``VARCHAR`` or a changed default produces a diff instead of silently drifting.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injected at runtime rather than committed to alembic.ini, so the password never
# reaches version control.
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Exclude database objects Alembic must not manage.

    ``v_trainer_scoring_facts`` is created by hand in migration 0003. Alembic reflects
    views as tables and would otherwise propose dropping it on every autogenerate run.

    Args:
        obj: The schema object under consideration.
        name: Its name.
        type_: Its kind, e.g. ``"table"`` or ``"index"``.
        reflected: Whether it came from the database rather than the metadata.
        compare_to: The object being compared against, if any.

    Returns:
        True to include the object in the comparison.
    """
    is_hand_written_view = type_ == "table" and name is not None and name.startswith("v_")
    return not is_hand_written_view


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting, for review or manual application."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations on an established synchronous connection.

    Args:
        connection: The connection supplied by ``run_sync``.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async engine and run the migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
