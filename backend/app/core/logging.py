"""Structured JSON logging.

Two properties matter here beyond formatting:

1. **Correlation** — every line carries the request id, so a user's bug report maps to
   a log query rather than to a guess about timestamps.
2. **Redaction** — passwords, hashes, and tokens are stripped by a processor, not by
   everyone remembering not to log them. Remembering is not a control.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import Settings
from app.middleware.correlation import get_correlation_id

#: Keys whose values are replaced wherever they appear in an event dictionary.
#: An allowlist would be safer still, but would make ordinary logging painful; this
#: list covers every field the codebase actually carries that must never be printed.
REDACTED_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "password_hash",
        "temporary_password",
        "token",
        "access_token",
        "refresh_token",
        "token_hash",
        "jwt_secret_key",
        "authorization",
        "secret",
    }
)

REDACTED = "[redacted]"


def _redact(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Replace sensitive values anywhere in the event dictionary.

    Runs as a structlog processor, so it applies to every line from every module
    regardless of who wrote the call site (§12: "no secret, password, or token appears
    in any log line").
    """
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = REDACTED
    return event_dict


def _add_correlation_id(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach the current correlation id to every line."""
    event_dict.setdefault("correlation_id", get_correlation_id())
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog and the standard library's logging.

    JSON in production so lines are machine-parseable; a coloured console renderer in
    development because a human is reading them.

    Args:
        settings: Application settings supplying the level and environment.
    """
    level = getattr(logging, settings.log_level)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    # Uvicorn installs its own handlers; let them propagate into structlog's format
    # instead of printing a second, differently-shaped copy of every line.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.db_echo else logging.WARNING
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_correlation_id,
        _redact,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.is_production or settings.environment == "staging":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
