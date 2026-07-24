"""``StrEnum`` mirrors of every ``CHECK``-constrained value set in the schema.

Status values are stored as ``VARCHAR`` + ``CHECK``, not as native PostgreSQL
``ENUM`` types (§4, ADR-0004). Altering a native enum cannot be done cleanly in a
reversible migration — ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction
block before PostgreSQL 12 and still cannot be *removed* at all — and these value
sets will change as the system matures.

The trade-off is that the ORM and the database now hold the same list in two
places. That is what this module is for: each enum is the Python side of exactly one
``CHECK``, and :func:`values_of` is what the model modules pass to the constraint, so
the two cannot drift.

Values that carry **weight in the scoring algorithm** are not here. They live in
lookup tables (``qualification_levels``, ``proficiency_levels``) because they need an
ordering and a score attached, and because NFR-10 requires retuning them without a
deployment (§5.1).

Every value below is verified against ``frontend/src/types/domain.ts``, which is a
binding contract.
"""

from __future__ import annotations

from enum import StrEnum


def values_of(enum_cls: type[StrEnum]) -> list[str]:
    """Return an enum's values, for building a ``CHECK ... IN (...)`` constraint.

    Args:
        enum_cls: The enum to enumerate.

    Returns:
        The member values in declaration order.
    """
    return [member.value for member in enum_cls]


def check_in(column: str, enum_cls: type[StrEnum]) -> str:
    """Build the SQL text for a ``CHECK (column IN (...))`` constraint.

    Generating the clause from the enum is what stops the Python and SQL value sets
    from drifting: adding a member here changes the constraint on the next
    autogenerate, and a migration diff appears where a silent mismatch used to.

    Args:
        column: The column name to constrain.
        enum_cls: The enum supplying the permitted values.

    Returns:
        SQL suitable for :class:`sqlalchemy.CheckConstraint`.

    Example:
        >>> check_in("account_status", AccountStatus)
        "account_status IN ('ACTIVE', 'SUSPENDED', 'DEACTIVATED')"
    """
    permitted = ", ".join(f"'{value}'" for value in values_of(enum_cls))
    return f"{column} IN ({permitted})"


class RoleName(StrEnum):
    """The four SRS actors. Mirrors ``domain.ts:RoleName``."""

    TRAINING_ADMINISTRATOR = "TRAINING_ADMINISTRATOR"
    TRAINING_OFFICER = "TRAINING_OFFICER"
    TRAINER = "TRAINER"
    SYSTEM_ADMINISTRATOR = "SYSTEM_ADMINISTRATOR"


class ManagementLevel(StrEnum):
    """UPF rank bands (§5.1 ``police_ranks.management_level``)."""

    STRATEGIC = "STRATEGIC"
    SENIOR = "SENIOR"
    MIDDLE = "MIDDLE"
    JUNIOR = "JUNIOR"


class StationType(StrEnum):
    """Kinds of UPF establishment (§5.1 ``stations.station_type``)."""

    HEADQUARTERS = "HEADQUARTERS"
    DIVISIONAL = "DIVISIONAL"
    STATION = "STATION"
    POST = "POST"
    TRAINING_INSTITUTION = "TRAINING_INSTITUTION"
    SPECIALISED_UNIT = "SPECIALISED_UNIT"


class InstitutionType(StrEnum):
    """Where a qualification was obtained (§5.1 ``institutions.institution_type``).

    ``POLICE`` is load-bearing, not descriptive: the QUALIFICATION criterion awards a
    +8 bonus for a qualification from a police training institution. The frontend
    implements this by matching against a hard-coded set of institution *names*
    (``POLICE_INSTITUTIONS`` in ``lib/constants.ts``), which fails silently on a
    spelling variant. Here it is a column, so the rule is structural.
    """

    POLICE = "POLICE"
    UNIVERSITY = "UNIVERSITY"
    PROFESSIONAL = "PROFESSIONAL"
    INTERNATIONAL = "INTERNATIONAL"


class AccountStatus(StrEnum):
    """User account state. Mirrors ``domain.ts:AccountStatus``."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class AvailabilityStatus(StrEnum):
    """Trainer availability. Mirrors ``domain.ts:AvailabilityStatus``.

    ``UNAVAILABLE`` is the BR-03 exclusion gate — the first rule applied in a
    prediction run, before any scoring happens.
    """

    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    UNAVAILABLE = "UNAVAILABLE"


class UnavailabilityCategory(StrEnum):
    """Why a trainer is absent (§5.3 ``trainer_unavailability.category``)."""

    LEAVE = "LEAVE"
    COURT = "COURT"
    DEPLOYMENT = "DEPLOYMENT"
    STUDY = "STUDY"
    MEDICAL = "MEDICAL"
    OTHER = "OTHER"


class ProgrammeStatus(StrEnum):
    """Training programme lifecycle. Mirrors ``domain.ts:ProgrammeStatus``.

    The ``DRAFT`` → ``REQUIREMENTS_SET`` transition is meaningful precisely because
    ``training_programmes.required_specialization_area_id`` is nullable until FR-05
    requirements are defined.
    """

    DRAFT = "DRAFT"
    REQUIREMENTS_SET = "REQUIREMENTS_SET"
    PREDICTED = "PREDICTED"
    AWAITING_RESPONSE = "AWAITING_RESPONSE"
    ALLOCATED = "ALLOCATED"
    CONDUCTED = "CONDUCTED"
    EVALUATED = "EVALUATED"
    CANCELLED = "CANCELLED"


class CriterionKey(StrEnum):
    """The five scoring criteria. Mirrors ``domain.ts:CriterionKey``.

    This enum names the criteria that exist; their **weights** are rows in
    ``scoring_policy_weights`` (D8). Adding a sixth criterion means adding a member
    here and a row there — not a schema migration.
    """

    SPECIALIZATION = "SPECIALIZATION"
    QUALIFICATION = "QUALIFICATION"
    EXPERIENCE = "EXPERIENCE"
    PERFORMANCE = "PERFORMANCE"
    AVAILABILITY = "AVAILABILITY"


class ConfidenceBand(StrEnum):
    """Confidence bucket. Mirrors ``domain.ts:ConfidenceBand``.

    Confidence here measures **data completeness**, not statistical confidence. A
    ``LOW`` band means "we know little about this trainer", which is the honest
    caveat the SRS requires the UI to surface.
    """

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class DataQuality(StrEnum):
    """Per-criterion data quality flag inside a ``CriterionScore``.

    Not a column: it lives inside the ``breakdown`` JSONB. Declared here so the seed
    and Phase 2 emit the same spellings.
    """

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class ExclusionReason(StrEnum):
    """Why a trainer was gated out. Mirrors ``domain.ts:ExclusionReason``."""

    UNAVAILABLE = "UNAVAILABLE"
    MISSING_SPECIALIZATION = "MISSING_SPECIALIZATION"
    BELOW_MINIMUM_EXPERIENCE = "BELOW_MINIMUM_EXPERIENCE"
    BELOW_MINIMUM_QUALIFICATION = "BELOW_MINIMUM_QUALIFICATION"
    SCHEDULE_CONFLICT = "SCHEDULE_CONFLICT"


class BusinessRule(StrEnum):
    """The rule citation recorded against an exclusion.

    Mirrors ``domain.ts:ExcludedTrainer.businessRule``. Storing the citation turns
    the Exclusion Ledger into an auditable artefact: an officer asking "why isn't
    so-and-so on the list?" gets the rule number, not an opinion.
    """

    BR_03 = "BR-03"
    BR_04 = "BR-04"
    FR_05 = "FR-05"


class AllocationStatus(StrEnum):
    """Allocation lifecycle. Mirrors ``domain.ts:AllocationStatus``."""

    PENDING_TRAINER = "PENDING_TRAINER"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CONDUCTED = "CONDUCTED"
    EVALUATED = "EVALUATED"
    WITHDRAWN = "WITHDRAWN"


class AuditAction(StrEnum):
    """Auditable actions (§5.8).

    A **superset** of ``domain.ts:AuditAction``. ``TOKEN_REFRESHED``,
    ``PROFILE_UPDATED``, and ``AVAILABILITY_CHANGED`` are required by §5.8 but absent
    from the frontend union — recorded as conflict C8 in ``PROGRESS.md``. The seed
    emits none of the three, so no seeded row can break the frontend contract; the
    union gains them in Phase 3.
    """

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    PROGRAMME_CREATED = "PROGRAMME_CREATED"
    REQUIREMENTS_DEFINED = "REQUIREMENTS_DEFINED"
    REQUIREMENTS_CHANGED = "REQUIREMENTS_CHANGED"
    PREDICTION_GENERATED = "PREDICTION_GENERATED"
    WEIGHTS_SIMULATED = "WEIGHTS_SIMULATED"
    WEIGHTS_SAVED = "WEIGHTS_SAVED"
    ALLOCATION_APPROVED = "ALLOCATION_APPROVED"
    ALLOCATION_DECLINED = "ALLOCATION_DECLINED"
    CANDIDATE_SKIPPED = "CANDIDATE_SKIPPED"
    ASSIGNMENT_ACCEPTED = "ASSIGNMENT_ACCEPTED"
    ASSIGNMENT_DECLINED = "ASSIGNMENT_DECLINED"
    EVALUATION_RECORDED = "EVALUATION_RECORDED"
    REPORT_EXPORTED = "REPORT_EXPORTED"
    USER_CREATED = "USER_CREATED"
    USER_MODIFIED = "USER_MODIFIED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    ROLE_CHANGED = "ROLE_CHANGED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    AVAILABILITY_CHANGED = "AVAILABILITY_CHANGED"
    UNAUTHORISED_ATTEMPT = "UNAUTHORISED_ATTEMPT"


class NotificationType(StrEnum):
    """Notification category. Mirrors ``domain.ts:NotificationType``."""

    ASSIGNMENT = "ASSIGNMENT"
    APPROVAL = "APPROVAL"
    EVALUATION = "EVALUATION"
    SYSTEM = "SYSTEM"
    REMINDER = "REMINDER"


class NotificationStatus(StrEnum):
    """Read state. Mirrors ``domain.ts:Notification.status``."""

    UNREAD = "UNREAD"
    READ = "READ"


class DeliveryStatus(StrEnum):
    """Delivery state of a notification (§5.8)."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
