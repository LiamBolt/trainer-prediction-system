"""Scoring policy management (§6.6, NFR-10).

Imports no `fastapi` (B7).

**A policy is versioned, never edited.** Saving new weights creates a new version and
deactivates the previous one. Historical prediction runs stored their weights at the
time, so an old ranking stays interpretable against the policy that actually produced
it — which is the difference between an auditable decision and one that merely looked
right when it was made.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import AuditAction, CriterionKey
from app.models.identity import User
from app.models.scoring import ScoringPolicy, ScoringPolicyWeight
from app.schemas.scoring import ScoringPolicyRead, ScoringPolicyUpdate, WeightRead

#: Plain-English descriptions shown beside each slider in the Weight Studio. Stored on
#: the row so an administrator retuning a weight can also correct the sentence that
#: explains it, without a release.
DEFAULT_DESCRIPTIONS: dict[str, str] = {
    "SPECIALIZATION": (
        "How closely the trainer's proven area of expertise matches what this course requires."
    ),
    "PERFORMANCE": "The trainer's average rating from courses they have delivered before.",
    "EXPERIENCE": "Length of service, counted up to a twenty-year ceiling.",
    "QUALIFICATION": "The trainer's highest formal academic or professional qualification.",
    "AVAILABILITY": "How much spare teaching capacity the trainer has right now.",
}

DEFAULT_LABELS: dict[str, str] = {
    "SPECIALIZATION": "Specialisation match",
    "PERFORMANCE": "Proven performance",
    "EXPERIENCE": "Years of service",
    "QUALIFICATION": "Qualification",
    "AVAILABILITY": "Availability",
}

SORT_ORDER: dict[str, int] = {
    "SPECIALIZATION": 1,
    "PERFORMANCE": 2,
    "EXPERIENCE": 3,
    "QUALIFICATION": 4,
    "AVAILABILITY": 5,
}


class ScoringPolicyService:
    """Reads and versions the scoring policy.

    Args:
        session: The request's session.
        audit: Audit service sharing the same transaction.
        clock: Injected clock.
    """

    def __init__(self, session: AsyncSession, audit: object, clock: Clock) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock

    async def _load(self, policy_id: int) -> ScoringPolicyRead:
        """Load one policy with its weights."""
        header = await self._session.execute(
            select(
                ScoringPolicy.policy_id,
                ScoringPolicy.version,
                ScoringPolicy.name,
                ScoringPolicy.is_active,
                ScoringPolicy.effective_from,
                ScoringPolicy.notes,
                ScoringPolicy.created_by_user_id.label("created_by"),
                User.full_name.label("created_by_name"),
            )
            .outerjoin(User, User.user_id == ScoringPolicy.created_by_user_id)
            .where(ScoringPolicy.policy_id == policy_id)
        )
        row = header.one_or_none()
        if row is None:
            raise NotFoundError("That scoring policy could not be found.")

        weights = await self._session.execute(
            select(
                ScoringPolicyWeight.criterion_key,
                ScoringPolicyWeight.display_label,
                ScoringPolicyWeight.weight,
                ScoringPolicyWeight.description,
                ScoringPolicyWeight.sort_order,
            )
            .where(ScoringPolicyWeight.policy_id == policy_id)
            .order_by(ScoringPolicyWeight.sort_order)
        )
        return ScoringPolicyRead(
            policy_id=row.policy_id,
            version=row.version,
            name=row.name,
            is_active=row.is_active,
            effective_from=row.effective_from,
            notes=row.notes,
            created_by=row.created_by,
            created_by_name=row.created_by_name,
            weights=[WeightRead.model_validate(w) for w in weights.all()],
        )

    async def get_active(self) -> ScoringPolicyRead:
        """Return the active policy.

        Returns:
            The active policy with its weights.

        Raises:
            ConflictError: If none is active. A partial unique index makes more than
                one impossible; none at all means the system was never configured.
        """
        result = await self._session.execute(
            select(ScoringPolicy.policy_id).where(ScoringPolicy.is_active)
        )
        policy_id = result.scalar_one_or_none()
        if policy_id is None:
            raise ConflictError(
                "No scoring policy is active. A System Administrator must configure "
                "the weighting before rankings can be generated."
            )
        return await self._load(policy_id)

    async def history(self) -> list[ScoringPolicyRead]:
        """Return every policy version, newest first."""
        result = await self._session.execute(
            select(ScoringPolicy.policy_id).order_by(ScoringPolicy.version.desc())
        )
        return [await self._load(pid) for pid in result.scalars().all()]

    async def save_new_version(
        self, payload: ScoringPolicyUpdate, actor_user_id: int
    ) -> ScoringPolicyRead:
        """Create a new policy version and deactivate the previous (NFR-10).

        The weights must cover **all five** criteria and total exactly 100. The
        database's deferred trigger enforces the total but permits a policy with a
        subset of criteria (ADR-0011 states that limit plainly); this is the layer that
        closes it, because a policy missing a criterion would silently score every
        trainer out of less than 100.

        Args:
            payload: The new weights.
            actor_user_id: Who saved them.

        Returns:
            The new active policy.

        Raises:
            ValidationError: If a criterion is missing or unknown.
        """
        supplied = {w.criterion_key for w in payload.weights}
        expected = {key.value for key in CriterionKey}
        missing = expected - supplied
        if missing:
            raise ValidationError(
                "Every criterion must be given a weight. Missing: "
                + ", ".join(sorted(missing))
                + ".",
                errors=[{"field": "weights", "message": "All five criteria are required."}],
            )

        previous = await self.get_active()

        highest = await self._session.execute(
            select(ScoringPolicy.version).order_by(ScoringPolicy.version.desc()).limit(1)
        )
        next_version = int(highest.scalar_one_or_none() or 0) + 1

        # Deactivate first: the partial unique index permits only one active policy,
        # so inserting the new one while the old is still active would violate it.
        await self._session.execute(
            update(ScoringPolicy).where(ScoringPolicy.is_active).values(is_active=False)
        )
        await self._session.flush()

        policy = ScoringPolicy(
            version=next_version,
            name=payload.name,
            is_active=True,
            effective_from=self._clock.now(),
            notes=payload.notes,
            created_by_user_id=actor_user_id,
        )
        self._session.add(policy)
        await self._session.flush()

        self._session.add_all(
            [
                ScoringPolicyWeight(
                    policy_id=policy.policy_id,
                    criterion_key=w.criterion_key,
                    display_label=DEFAULT_LABELS.get(w.criterion_key, w.criterion_key.title()),
                    weight=w.weight,
                    description=DEFAULT_DESCRIPTIONS.get(w.criterion_key, ""),
                    sort_order=SORT_ORDER.get(w.criterion_key, 99),
                )
                for w in payload.weights
            ]
        )
        await self._session.flush()

        from app.services.audit_service import AuditService

        assert isinstance(self._audit, AuditService)
        await self._audit.record(
            AuditAction.WEIGHTS_SAVED,
            entity_type="SCORING_POLICY",
            entity_id=policy.policy_id,
            before={w.criterion_key: float(w.weight) for w in previous.weights},
            after={w.criterion_key: float(w.weight) for w in payload.weights},
            detail=(
                f"Adopted policy version {next_version} ('{payload.name}'). "
                f"Version {previous.version} deactivated. Existing rankings keep the "
                "weights that produced them."
            ),
        )
        return await self._load(policy.policy_id)

    @staticmethod
    def parse_override(raw: dict[str, Decimal]) -> dict[CriterionKey, Decimal]:
        """Convert client-supplied weights into engine keys.

        Args:
            raw: Criterion key strings to weights.

        Returns:
            Typed weights.

        Raises:
            ValidationError: If a key is not a known criterion.
        """
        parsed: dict[CriterionKey, Decimal] = {}
        for key, value in raw.items():
            try:
                parsed[CriterionKey(key)] = value
            except ValueError as exc:
                raise ValidationError(
                    f"'{key}' is not a scoring criterion.",
                    errors=[{"field": f"weights.{key}", "message": "Unknown criterion."}],
                ) from exc
        return parsed
