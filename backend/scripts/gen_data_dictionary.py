"""Generate ``docs/DATA-DICTIONARY.md`` from the live database (§8).

Run with ``python -m scripts.gen_data_dictionary``.

The dictionary is **generated, never hand-maintained**. A hand-written data
dictionary is out of date the day after it is written, and the version everybody
quotes is always the stale one. Reading it out of ``information_schema`` joined to
``pg_description`` means the document cannot disagree with the database: the
``comment=`` on each model column is the single source, it lands in
``pg_description`` at migration time, and it is read back from there here.
"""

from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine, session_scope

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "DATA-DICTIONARY.md"

TABLE_QUERY = text(
    """
    SELECT c.relname AS table_name,
           obj_description(c.oid, 'pg_class') AS table_comment,
           CAST(c.relkind AS text) AS kind
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind IN ('r', 'v')
      AND c.relname <> 'alembic_version'
    ORDER BY c.relkind ASC, c.relname
    """
)

COLUMN_QUERY = text(
    """
    SELECT a.attname                                              AS column_name,
           format_type(a.atttypid, a.atttypmod)                   AS data_type,
           a.attnotnull                                           AS not_null,
           pg_get_expr(d.adbin, d.adrelid)                        AS default_expr,
           col_description(a.attrelid, a.attnum)                  AS comment,
           a.attidentity <> ''                                    AS is_identity
    FROM pg_attribute a
    LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
    WHERE a.attrelid = CAST(:relname AS regclass)
      AND a.attnum > 0
      AND NOT a.attisdropped
    ORDER BY a.attnum
    """
)

CONSTRAINT_QUERY = text(
    """
    SELECT conname AS name,
           contype AS kind,
           pg_get_constraintdef(oid) AS definition
    FROM pg_constraint
    WHERE conrelid = CAST(:relname AS regclass)
    ORDER BY contype, conname
    """
)

INDEX_QUERY = text(
    """
    SELECT indexname AS name, indexdef AS definition
    FROM pg_indexes
    WHERE schemaname = 'public' AND tablename = :relname
    ORDER BY indexname
    """
)

ROUTINE_QUERY = text(
    """
    SELECT p.proname AS name,
           pg_get_function_identity_arguments(p.oid) AS args,
           obj_description(p.oid, 'pg_proc') AS comment
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname IN ('set_updated_at', 'prevent_audit_mutation',
                        'check_policy_weights_sum', 'next_registry_number')
    ORDER BY p.proname
    """
)

TRIGGER_QUERY = text(
    """
    SELECT c.relname AS table_name, t.tgname AS name,
           pg_get_triggerdef(t.oid) AS definition
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT t.tgisinternal AND n.nspname = 'public'
      AND t.tgname NOT LIKE '%set_updated_at'
    ORDER BY c.relname, t.tgname
    """
)

CONSTRAINT_KIND = {
    "p": "PRIMARY KEY",
    "f": "FOREIGN KEY",
    "u": "UNIQUE",
    "c": "CHECK",
    "x": "EXCLUDE",
}


def _escape(value: str | None) -> str:
    """Escape pipe characters so a value cannot break the Markdown table."""
    if not value:
        return ""
    return value.replace("|", "\\|").replace("\n", " ").strip()


async def build() -> str:
    """Query the live database and render the dictionary as Markdown."""
    settings = get_settings()
    lines: list[str] = []
    generated = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# TPS Data Dictionary")
    lines.append("")
    lines.append(
        "> **Generated file — do not edit by hand.** Produced by "
        "`python -m scripts.gen_data_dictionary`, read directly from the live "
        "database via `information_schema` and `pg_description`."
    )
    lines.append(">")
    lines.append(f"> Database `{settings.postgres_db}` · generated {generated}")
    lines.append("")
    lines.append(
        "Every description below originates as a `comment=` on a SQLAlchemy column or "
        "table in `app/models/`, which Alembic writes into `pg_description`. The "
        "models are the single source of truth (D1); this document is a projection of "
        "them, taken from the database rather than from the code, so it reflects what "
        "was actually migrated."
    )
    lines.append("")

    async with session_scope() as session:
        objects = list((await session.execute(TABLE_QUERY)).all())
        tables = [o for o in objects if o.kind == "r"]
        views = [o for o in objects if o.kind == "v"]

        lines.append(f"**{len(tables)} tables · {len(views)} view**")
        lines.append("")
        lines.append("## Contents")
        lines.append("")
        for obj in objects:
            anchor = obj.table_name.replace("_", "-")
            label = "view" if obj.kind == "v" else "table"
            lines.append(f"- [`{obj.table_name}`](#{anchor}) — {label}")
        lines.append("")

        for obj in objects:
            kind_label = "View" if obj.kind == "v" else "Table"
            lines.append("---")
            lines.append("")
            lines.append(f"## {obj.table_name}")
            lines.append("")
            lines.append(f"*{kind_label}.* {_escape(obj.table_comment) or '_No description._'}")
            lines.append("")

            columns = list((await session.execute(COLUMN_QUERY, {"relname": obj.table_name})).all())
            lines.append("| Column | Type | Null | Default | Description |")
            lines.append("|---|---|---|---|---|")
            for column in columns:
                nullable = "NOT NULL" if column.not_null else "NULL"
                default = (
                    "identity" if column.is_identity else (_escape(column.default_expr) or "—")
                )
                lines.append(
                    f"| `{column.column_name}` | `{column.data_type}` | {nullable} "
                    f"| {default} | {_escape(column.comment)} |"
                )
            lines.append("")

            if obj.kind != "r":
                continue

            constraints = list(
                (await session.execute(CONSTRAINT_QUERY, {"relname": obj.table_name})).all()
            )
            if constraints:
                lines.append("**Constraints**")
                lines.append("")
                lines.append("| Name | Kind | Definition |")
                lines.append("|---|---|---|")
                for constraint in constraints:
                    kind = CONSTRAINT_KIND.get(constraint.kind, constraint.kind)
                    lines.append(
                        f"| `{constraint.name}` | {kind} | `{_escape(constraint.definition)}` |"
                    )
                lines.append("")

            indexes = list((await session.execute(INDEX_QUERY, {"relname": obj.table_name})).all())
            if indexes:
                lines.append("**Indexes**")
                lines.append("")
                for index in indexes:
                    lines.append(f"- `{index.name}` — `{_escape(index.definition)}`")
                lines.append("")

        # --- Functions and triggers ---------------------------------------
        lines.append("---")
        lines.append("")
        lines.append("## Functions")
        lines.append("")
        lines.append("| Function | Description |")
        lines.append("|---|---|")
        for routine in (await session.execute(ROUTINE_QUERY)).all():
            signature = f"{routine.name}({routine.args})"
            lines.append(f"| `{signature}` | {_escape(routine.comment)} |")
        lines.append("")

        lines.append("## Triggers")
        lines.append("")
        lines.append(
            "The shared `set_updated_at` triggers are omitted — one exists on every "
            "table carrying `updated_at`, and listing 23 identical rows would only "
            "obscure the two that matter."
        )
        lines.append("")
        lines.append("| Table | Trigger | Definition |")
        lines.append("|---|---|---|")
        for trigger in (await session.execute(TRIGGER_QUERY)).all():
            lines.append(
                f"| `{trigger.table_name}` | `{trigger.name}` | `{_escape(trigger.definition)}` |"
            )
        lines.append("")

        lines.append("## Sequences")
        lines.append("")
        lines.append(
            "Registry sequences back `next_registry_number()` (§5.9). **Gaps are "
            "expected**: a sequence does not roll back with its transaction. A registry "
            "number is an identifier, not a count, so a gap carries no meaning and must "
            "not be repaired — renumbering would change identifiers on documents that "
            "have already been issued."
        )
        lines.append("")
        rows = await session.execute(
            text(
                "SELECT sequencename, last_value FROM pg_sequences "
                "WHERE schemaname = 'public' AND sequencename LIKE 'registry%' "
                "ORDER BY sequencename"
            )
        )
        lines.append("| Sequence | Last value |")
        lines.append("|---|---|")
        for name, last_value in rows.all():
            lines.append(f"| `{name}` | {last_value if last_value is not None else '—'} |")
        lines.append("")

    return "\n".join(lines) + "\n"


async def main() -> int:
    """Write the dictionary to ``docs/DATA-DICTIONARY.md``."""
    content = await build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(OUTPUT.parent.parent)} ({len(content):,} bytes)")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
