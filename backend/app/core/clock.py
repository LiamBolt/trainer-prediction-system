"""An injectable clock.

**Never call `datetime.now()` inside a service.** A service that reads the wall clock
internally cannot be tested deterministically, and this system has three behaviours
that depend on time in ways that must be provable: the fifteen-minute account lockout
(FR-01), refresh-token expiry (B5), and the recency component of prediction confidence
(§5.6).

Pass a :class:`Clock` and tests can freeze it.
"""

from __future__ import annotations

import datetime
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Anything that can tell the time.

    A ``Protocol`` rather than a base class so a test can pass a plain lambda or a
    frozen stub without inheriting anything.
    """

    def now(self) -> datetime.datetime:
        """Return the current instant as an aware UTC datetime."""
        ...


class SystemClock:
    """The real clock, reading UTC from the operating system."""

    def now(self) -> datetime.datetime:
        """Return the current instant in UTC.

        Always timezone-aware (D5). A naive datetime compared against a
        ``TIMESTAMPTZ`` column is a bug that surfaces as an off-by-three-hours error
        in Kampala and never in a UTC test environment.

        Returns:
            The current UTC time.
        """
        return datetime.datetime.now(tz=datetime.UTC)


class FrozenClock:
    """A clock stuck at a fixed instant, for tests.

    Args:
        instant: The time to report. Must be timezone-aware.

    Raises:
        ValueError: If ``instant`` is naive.
    """

    def __init__(self, instant: datetime.datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FrozenClock requires an aware datetime; naive input is a bug.")
        self._instant = instant

    def now(self) -> datetime.datetime:
        """Return the frozen instant."""
        return self._instant

    def advance(self, **delta: float) -> None:
        """Move the clock forward.

        Args:
            **delta: Keyword arguments accepted by :class:`datetime.timedelta`.
        """
        self._instant += datetime.timedelta(**delta)


#: The process-wide clock. Overridden per request in tests via a dependency override.
system_clock = SystemClock()


def to_local(
    instant: datetime.datetime, timezone_name: str = "Africa/Kampala"
) -> datetime.datetime:
    """Convert a UTC instant to the application timezone for display.

    Storage is UTC and serialisation carries an offset (§4.3); this exists for log
    lines and generated documents that a human reads in local time.

    Args:
        instant: An aware datetime.
        timezone_name: IANA timezone name.

    Returns:
        The same instant expressed in the target timezone.
    """
    return instant.astimezone(ZoneInfo(timezone_name))
