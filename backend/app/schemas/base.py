"""The Pydantic base every schema inherits (B2).

**camelCase on the wire, snake_case in Python.** The frontend expects
``predictionScore``, ``forceNumber``, ``rankPosition``; Python and PostgreSQL are
snake_case. The translation happens here, in one alias generator, and nowhere else —
database columns and Python attributes are never renamed to shortcut it.

``populate_by_name=True`` means schemas accept **either** spelling on input, so a
client sending snake_case is not rejected for a cosmetic reason, while output is always
camelCase.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every request and response schema.

    - ``alias_generator=to_camel`` renders ``prediction_score`` as ``predictionScore``.
    - ``populate_by_name=True`` accepts both spellings on input.
    - ``from_attributes=True`` allows construction from an ORM object via
      ``model_validate``, which is how repositories hand rows to routers without the
      ORM entity itself ever crossing the boundary (B3).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        ser_json_timedelta="iso8601",
        validate_assignment=True,
    )


def _serialise_score(value: Decimal | None) -> float | None:
    """Serialise a score as a JSON number, quantised to two places first.

    §4.3 requires a decision here, stated and applied consistently. The choice is
    **numbers, not strings**, because `frontend/src/types/domain.ts` types every score
    as `number` and that contract is binding.

    The quantisation happens *before* encoding. `Decimal("87.40")` becomes `87.4`, not
    `87.40000000000001`: the value is rounded to two places while it is still exact,
    and only then converted. Arithmetic never touches a float — see ADR-0014 and
    `docs/ALGORITHMS.md` §10.

    Args:
        value: The exact decimal, or None.

    Returns:
        A JSON-safe float, or None.
    """
    if value is None:
        return None
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


#: A 0–100 score serialised as a two-decimal JSON number.
ScoreField = Annotated[Decimal, PlainSerializer(_serialise_score, return_type=float)]

#: An optional score.
OptionalScoreField = Annotated[
    Decimal | None, PlainSerializer(_serialise_score, return_type=float | None)
]


def _serialise_rating(value: Decimal | None) -> float | None:
    """Serialise a 1.0–5.0 evaluation rating to one decimal place."""
    if value is None:
        return None
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


#: An evaluation rating serialised as a one-decimal JSON number.
RatingField = Annotated[Decimal, PlainSerializer(_serialise_rating, return_type=float)]
OptionalRatingField = Annotated[
    Decimal | None, PlainSerializer(_serialise_rating, return_type=float | None)
]


class ORMModel(CamelModel):
    """A response schema built from an ORM row.

    Identical to :class:`CamelModel`; the separate name documents intent at the call
    site — this shape leaves the API, and is never accepted as input (B3).
    """

    @classmethod
    def from_orm_row(cls, row: Any) -> Any:
        """Build from an ORM object or a projection row.

        Args:
            row: An ORM entity or a SQLAlchemy ``Row``.

        Returns:
            The validated schema instance.
        """
        return cls.model_validate(row)


class Message(CamelModel):
    """A simple acknowledgement with a human-readable message.

    Used where an operation has no resource to return but the interface should still
    say what happened — the frontend echoes ``message`` to the user verbatim, so it is
    written for an officer, not a developer.
    """

    ok: bool = True
    message: str
