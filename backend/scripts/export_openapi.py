"""Export the OpenAPI schema to ``docs/openapi.json``.

Committed so that API changes appear as **reviewable diffs**. A schema that only exists
at runtime cannot be reviewed before it ships: a route whose role gate was widened, or a
field quietly added to a response, looks identical in a pull request whether it was
intended or not.

Run after any change to a route, schema, or dependency::

    uv run python -m scripts.export_openapi

Exits non-zero with ``--check`` when the committed file is stale, which is what a CI
step would use.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from app.main import create_app

OUTPUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "openapi.json"


def build() -> str:
    """Render the schema as stable, diff-friendly JSON.

    ``sort_keys`` and a two-space indent so an unrelated change to route registration
    order does not produce a thousand-line diff.

    Returns:
        The serialised schema, newline-terminated.
    """
    schema = create_app().openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    """Write or verify the exported schema.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed file is out of date. Writes nothing.",
    )
    args = parser.parse_args()

    rendered = build()

    if args.check:
        if not OUTPUT.exists():
            print(f"{OUTPUT} does not exist. Run: uv run python -m scripts.export_openapi")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != rendered:
            print(
                f"{OUTPUT} is out of date.\n"
                "The API surface changed without the schema being re-exported. Run:\n"
                "    uv run python -m scripts.export_openapi"
            )
            return 1
        print(f"{OUTPUT.name} is up to date.")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")

    schema = json.loads(rendered)
    operations = sum(
        1
        for operations in schema["paths"].values()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )
    print(
        f"Wrote {OUTPUT.relative_to(OUTPUT.parent.parent)} — "
        f"{len(schema['paths'])} paths, {operations} operations, "
        f"{len(schema.get('components', {}).get('schemas', {}))} schemas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
