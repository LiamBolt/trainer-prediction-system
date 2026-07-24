"""Reusable column types.

Centralised so that "a score" has one definition. If auditable precision ever needs
to change, it changes in one place and Alembic sees it across every table at once.
"""

from __future__ import annotations

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB

#: A 0–100 score with two decimal places. NUMERIC, never DOUBLE PRECISION (D4):
#: a government allocation decision must reproduce byte-for-byte years later, and
#: binary floating point cannot promise that. Maps to :class:`decimal.Decimal`.
Score = Numeric(5, 2)

#: A weight in the scoring policy, 0–100 with two decimals.
Weight = Numeric(5, 2)

#: An evaluation rating, 1.0–5.0 to one decimal place.
Rating = Numeric(2, 1)

#: Case-insensitive text for usernames and email addresses. Makes
#: ``G.Nabirye@upf.go.ug`` and ``g.nabirye@upf.go.ug`` the same identity, which is
#: what a user expects and what plain VARCHAR silently fails to deliver.
CaseInsensitiveText = CITEXT

#: Binary JSON for frozen snapshots and score breakdowns. JSONB, not JSON — JSON
#: stores the raw text including whitespace and cannot be indexed.
JsonB = JSONB

#: An IPv4/IPv6 address. Native INET, so range queries against an audit trail work
#: without string parsing.
IpAddress = INET


def short_text(length: int) -> String:
    """Return a bounded ``VARCHAR``.

    PostgreSQL does not reward short ``VARCHAR`` with storage savings, so a length
    here is a **domain assertion** — a rank code is 8 characters because ranks have
    short codes, not to save bytes.

    Args:
        length: Maximum character length.

    Returns:
        A configured :class:`sqlalchemy.String`.
    """
    return String(length)


__all__ = [
    "CaseInsensitiveText",
    "IpAddress",
    "JsonB",
    "Rating",
    "Score",
    "Weight",
    "short_text",
]
