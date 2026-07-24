"""The domain exception hierarchy.

Services raise these. **No service imports `fastapi` or raises `HTTPException`** (B7) —
one handler layer in :mod:`app.core.problem_details` translates every exception here
into an RFC 9457 response. If a service ever raises `HTTPException`, the layering has
already failed and the business logic has become untestable without a web framework.

Every ``detail`` is written for a **non-technical police officer**, not a developer.
"IP Sarah Mugisha is marked unavailable for these dates" — never "constraint violation
on availability_status". That text is rendered verbatim in the interface.
"""

from __future__ import annotations

from typing import Any


class TPSError(Exception):
    """Base class for every domain error.

    Attributes:
        detail: Human-readable explanation, written for an officer.
        status_code: The HTTP status this maps to.
        error_type: URI slug identifying the error class, used as the RFC 9457
            ``type`` member so clients can branch on a stable identifier rather than
            on prose.
        title: Short summary of the error class.
        errors: Optional per-field messages the frontend renders inline against form
            fields.
        extra: Additional top-level members merged into the problem document.
    """

    status_code: int = 500
    error_type: str = "internal-error"
    title: str = "Internal server error"

    def __init__(
        self,
        detail: str,
        *,
        errors: list[dict[str, str]] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []
        self.extra = extra


class NotFoundError(TPSError):
    """A requested resource does not exist."""

    status_code = 404
    error_type = "not-found"
    title = "Not found"


class ConflictError(TPSError):
    """The request conflicts with the current state of the resource."""

    status_code = 409
    error_type = "conflict"
    title = "Conflict with current state"


class ForbiddenError(TPSError):
    """The caller is authenticated but not permitted to do this.

    Distinct from :class:`UnauthorisedError`: 403 means "I know who you are, and no".
    """

    status_code = 403
    error_type = "forbidden"
    title = "Not permitted"


class UnauthorisedError(TPSError):
    """The caller is not authenticated, or the credential is invalid or expired.

    401 means "who are you". The message must never reveal whether a username exists —
    doing so turns the login endpoint into a user-enumeration oracle.
    """

    status_code = 401
    error_type = "unauthorised"
    title = "Authentication required"


class AccountLockedError(TPSError):
    """The account is locked after consecutive failed sign-ins (FR-01).

    423 rather than 401 because the credential may well be correct; the account is
    temporarily unusable, and the client needs to say so rather than prompt again.
    """

    status_code = 423
    error_type = "account-locked"
    title = "Account temporarily locked"

    def __init__(self, detail: str, *, retry_after_seconds: int, **extra: Any) -> None:
        super().__init__(detail, retryAfterSeconds=retry_after_seconds, **extra)
        self.retry_after_seconds = retry_after_seconds


class AccountDeactivatedError(TPSError):
    """The account has been deactivated by an administrator (FR-12).

    Deliberately distinct from a bad password: a deactivated user retyping their
    correct password forever is a support call nobody needs.
    """

    status_code = 403
    error_type = "account-deactivated"
    title = "Account deactivated"


class ValidationError(TPSError):
    """The request is well-formed but semantically invalid."""

    status_code = 422
    error_type = "validation-failed"
    title = "Validation failed"


class BusinessRuleViolation(ConflictError):  # noqa: N818 — name fixed by §7.5 of the spec
    """A named business rule forbids this operation.

    Carries the rule identifier so the frontend can render "Excluded under BR-03"
    rather than a generic conflict message. The rule number is the whole point: it
    turns a refusal into a citation an officer can look up.

    Attributes:
        rule: The rule identifier, e.g. ``"BR-03"``.
    """

    error_type = "business-rule-violation"
    title = "Business rule violation"

    def __init__(self, rule: str, detail: str, **extra: Any) -> None:
        super().__init__(detail, rule=rule, **extra)
        self.rule = rule


class DatabaseUnavailableError(TPSError):
    """The database could not be reached.

    Its own type because the remedy is specific and documented: on Linux the backend
    container reaches host PostgreSQL through ``host.docker.internal``, which requires
    both a ``host-gateway`` entry in Compose and PostgreSQL listening on the bridge.
    """

    status_code = 503
    error_type = "database-unavailable"
    title = "Database unavailable"
