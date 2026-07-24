"""Pagination helpers — offset for bounded tables, keyset for the audit log.

Two strategies, because they solve different problems:

- **Offset** (`page`/`pageSize`) for admin tables of bounded size. Simple, supports
  jumping to page 7, and the frontend's tables already expect it.
- **Keyset** (`?after=<cursor>`) for the audit log, which is append-only and unbounded.
  `OFFSET 200000` makes PostgreSQL read and discard two hundred thousand rows to
  return twenty; keyset seeks straight to the cursor. §6.11 requires it.

The list envelope in §4.1 is fixed and identical on every list endpoint. A client that
must handle two envelope shapes will mishandle one of them.
"""

from __future__ import annotations

import base64
import binascii
import datetime
import json
from collections.abc import Sequence
from math import ceil
from typing import Annotated, Any, Self

from fastapi import Depends
from pydantic import BaseModel, Field, model_validator

from app.core.exceptions import ValidationError

#: Hard ceiling on page size. Audit export streams instead of paginating.
MAX_PAGE_SIZE = 100

#: Beyond this offset, offset pagination is refused and keyset is required. Deep
#: offset paging is the failure mode this constant exists to prevent, not to permit.
MAX_OFFSET = 10_000


class PageParams(BaseModel):
    """Offset pagination and sort parameters.

    Attributes:
        page: 1-based page number.
        page_size: Rows per page, capped at :data:`MAX_PAGE_SIZE`.
        sort_by: Column to sort by. **Always validated against a per-endpoint
            allowlist** by :meth:`resolve_sort` — never interpolated raw.
        sort_dir: Sort direction.
    """

    page: int = Field(default=1, ge=1, description="1-based page number.", examples=[1])
    page_size: int = Field(
        default=20,
        ge=1,
        le=MAX_PAGE_SIZE,
        alias="pageSize",
        description=f"Rows per page, maximum {MAX_PAGE_SIZE}.",
        examples=[20],
    )
    sort_by: str | None = Field(
        default=None, alias="sortBy", description="Column to sort by.", examples=["fullName"]
    )
    sort_dir: str = Field(
        default="asc", alias="sortDir", pattern="^(asc|desc)$", description="asc or desc."
    )

    model_config = {"populate_by_name": True}

    @property
    def offset(self) -> int:
        """Row offset implied by ``page`` and ``page_size``."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Row limit."""
        return self.page_size

    def resolve_sort(self, allowed: dict[str, Any], default: Any) -> Any:
        """Resolve ``sort_by`` against an allowlist and apply the direction.

        The allowlist is the injection defence. SQLAlchemy parameterises values, but
        ``ORDER BY`` takes an identifier, not a value — a raw ``sortBy`` reaching the
        query is how ordering clauses become an injection vector.

        Args:
            allowed: Mapping of client-facing sort names to ORM columns.
            default: Column used when no ``sortBy`` was supplied.

        Returns:
            The ordering expression, with direction applied.

        Raises:
            ValidationError: If ``sort_by`` is not in the allowlist.
        """
        if self.sort_by is None:
            column = default
        elif self.sort_by in allowed:
            column = allowed[self.sort_by]
        else:
            raise ValidationError(
                f"Cannot sort by '{self.sort_by}'. Allowed: {', '.join(sorted(allowed))}.",
                errors=[{"field": "sortBy", "message": "Unsupported sort column."}],
            )
        return column.desc() if self.sort_dir == "desc" else column.asc()

    @model_validator(mode="after")
    def _reject_deep_offset(self) -> Self:
        """Refuse offsets deep enough to make the query pathological."""
        if self.offset > MAX_OFFSET:
            raise ValueError(
                f"Page {self.page} is too deep for offset paging (limit {MAX_OFFSET:,} rows). "
                "Narrow the filters, or use the cursor-based endpoint."
            )
        return self


class Page[T](BaseModel):
    """The list envelope from §4.1. Identical on every list endpoint.

    Attributes:
        items: The rows for this page.
        page: 1-based page number.
        page_size: Rows requested per page.
        total: Total rows matching the filters, across all pages.
        total_pages: Number of pages at this page size.
    """

    items: list[T]
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    model_config = {"populate_by_name": True}

    @classmethod
    def build(cls, items: Sequence[T], *, total: int, params: PageParams) -> Page[T]:
        """Assemble an envelope from a result set.

        Args:
            items: Rows for this page.
            total: Total matching rows.
            params: The pagination parameters used.

        Returns:
            The populated envelope.
        """
        return cls(
            items=list(items),
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=ceil(total / params.page_size) if params.page_size else 0,
        )

    @classmethod
    def empty(cls, params: PageParams) -> Page[T]:
        """Return an empty page, for filters that match nothing."""
        return cls(items=[], page=params.page, page_size=params.page_size, total=0, total_pages=0)


class CursorPage[T](BaseModel):
    """Keyset-paginated envelope for append-only tables (§6.11).

    Carries no ``total``: counting an unbounded append-only table on every request is
    precisely the cost keyset pagination exists to avoid.

    Attributes:
        items: The rows for this page.
        page_size: Rows requested.
        next_cursor: Opaque cursor for the following page, or None at the end.
        has_more: Whether more rows follow.
    """

    items: list[T]
    page_size: int = Field(serialization_alias="pageSize")
    next_cursor: str | None = Field(default=None, serialization_alias="nextCursor")
    has_more: bool = Field(default=False, serialization_alias="hasMore")

    model_config = {"populate_by_name": True}


def encode_cursor(created_at: datetime.datetime, row_id: int) -> str:
    """Encode a keyset cursor.

    The cursor is `(created_at, id)`, not `created_at` alone: timestamps collide, and a
    cursor that is not unique silently skips or repeats rows at page boundaries. The id
    breaks the tie.

    Args:
        created_at: The sort timestamp of the last row on the page.
        row_id: Its primary key.

    Returns:
        A URL-safe base64 cursor.
    """
    payload = json.dumps({"t": created_at.isoformat(), "i": row_id})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime.datetime, int]:
    """Decode a keyset cursor.

    Args:
        cursor: A cursor previously produced by :func:`encode_cursor`.

    Returns:
        The timestamp and row id it encodes.

    Raises:
        ValidationError: If the cursor is malformed. Cursors are opaque to clients, so
            a malformed one means it was tampered with or truncated — either way the
            request cannot be served and must say so plainly.
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return datetime.datetime.fromisoformat(payload["t"]), int(payload["i"])
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValidationError(
            "That page link is no longer valid. Please start from the first page.",
            errors=[{"field": "after", "message": "Malformed cursor."}],
        ) from exc


#: Reusable dependency annotation for offset pagination.
#:
#: ``Depends()`` rather than ``Query()``: with ``Query()`` FastAPI treats the model as a
#: single scalar parameter literally named ``params`` and rejects every request with
#: "field required". ``Depends()`` makes it inspect the model and expose each field —
#: ``page``, ``pageSize``, ``sortBy``, ``sortDir`` — as its own query parameter, which
#: is what the aliases are for.
PageQuery = Annotated[PageParams, Depends()]
