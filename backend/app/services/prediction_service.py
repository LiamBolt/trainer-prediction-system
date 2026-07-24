"""Prediction orchestration: fetch facts, run the engine, persist or discard (§5.8).

Imports no `fastapi` (B7).

**One engine, two callers.** ``run_and_persist`` writes a `prediction_run` and its
rows; ``simulate`` runs the identical function and writes nothing but an audit entry.
The difference is entirely in the caller. Duplicating the engine for simulation is
exactly how a Weight Studio preview silently diverges from what the server would
actually produce, and then an officer approves a ranking they never saw.
"""

from __future__ import annotations

import time
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.exceptions import BusinessRuleViolation, ConflictError, NotFoundError
from app.models.enums import AuditAction, CriterionKey, ProgrammeStatus
from app.models.identity import User
from app.models.prediction import Prediction, PredictionExclusion, PredictionRun
from app.models.programme import TrainingProgramme
from app.models.reference import QualificationLevel, SpecializationArea
from app.models.trainer import Trainer
from app.repositories.trainer_repo import TrainerRepository
from app.schemas.prediction import (
    CriterionScoreRead,
    ExclusionGroup,
    ExclusionRead,
    PredictionRead,
    PredictionRunRead,
    RankDelta,
)
from app.services.audit_service import AuditService
from app.services.prediction import (
    CandidateFacts,
    PredictionRunResult,
    ProgrammeRequirements,
    generate_prediction,
    preview_eligibility,
)
from app.services.prediction.criteria import DEFAULT_PRIOR_MEAN
from app.services.prediction.types import EligibilityPreview

logger = structlog.get_logger(__name__)


class PredictionService:
    """Runs the engine and persists its output.

    Args:
        session: The request's session.
        audit: Audit service sharing the same transaction (B8).
        clock: Injected clock.
        settings: Application settings, for the slow-run warning threshold.
    """

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._session = session
        self._audit = audit
        self._clock = clock
        self._settings = settings

    async def build_requirements(self, programme_id: int) -> ProgrammeRequirements:
        """Load a programme into the engine's input type.

        Args:
            programme_id: Primary key.

        Returns:
            The requirements.

        Raises:
            NotFoundError: If the programme does not exist.
            BusinessRuleViolation: If its requirements are not yet defined. FR-05
                forbids predicting without them — the engine would have nothing to
                match on and would rank the entire force.
        """
        result = await self._session.execute(
            select(
                TrainingProgramme.programme_id,
                TrainingProgramme.title,
                TrainingProgramme.required_specialization_area_id,
                SpecializationArea.name.label("required_specialization_name"),
                SpecializationArea.discipline_group,
                TrainingProgramme.minimum_experience,
                QualificationLevel.rank_order.label("minimum_qualification_order"),
                QualificationLevel.name.label("minimum_qualification_name"),
                TrainingProgramme.start_date,
                TrainingProgramme.end_date,
            )
            .outerjoin(
                SpecializationArea,
                SpecializationArea.specialization_area_id
                == TrainingProgramme.required_specialization_area_id,
            )
            .outerjoin(
                QualificationLevel,
                QualificationLevel.level_id == TrainingProgramme.minimum_qualification_level_id,
            )
            .where(TrainingProgramme.programme_id == programme_id)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("That training programme could not be found.")
        if row.required_specialization_area_id is None:
            raise BusinessRuleViolation(
                "FR-05",
                "This programme has no required specialisation yet. Define the "
                "requirements before generating a ranking — without them there is "
                "nothing to match trainers against.",
            )
        return ProgrammeRequirements(
            programme_id=row.programme_id,
            title=row.title,
            required_specialization_area_id=row.required_specialization_area_id,
            required_specialization_name=row.required_specialization_name,
            discipline_group=row.discipline_group,
            minimum_experience=row.minimum_experience,
            minimum_qualification_order=row.minimum_qualification_order,
            minimum_qualification_name=row.minimum_qualification_name,
            start_date=row.start_date,
            end_date=row.end_date,
        )

    async def _fetch_facts(
        self, programme: ProgrammeRequirements
    ) -> tuple[list[CandidateFacts], Decimal]:
        """Fetch the candidate pool and the shrinkage prior.

        Args:
            programme: The requirements.

        Returns:
            The facts and the prior mean.
        """
        repo = TrainerRepository(self._session)
        facts = await repo.fetch_scoring_facts(
            area_id=programme.required_specialization_area_id,
            discipline_group=programme.discipline_group,
            programme_id=programme.programme_id,
            start_date=programme.start_date,
            end_date=programme.end_date,
        )
        prior = await repo.prior_mean()
        return facts, prior if prior is not None else DEFAULT_PRIOR_MEAN

    async def active_weights(self) -> tuple[dict[CriterionKey, Decimal], int | None]:
        """Load the weights from the active scoring policy.

        Weights are **never hard-coded** — NFR-10 requires them to be retunable
        without a deployment, so they are read on every run.

        Returns:
            The weights and the policy id.

        Raises:
            ConflictError: If no active policy exists.
        """
        from app.models.scoring import ScoringPolicy, ScoringPolicyWeight

        result = await self._session.execute(
            select(
                ScoringPolicyWeight.criterion_key,
                ScoringPolicyWeight.weight,
                ScoringPolicy.policy_id,
            )
            .join(ScoringPolicy, ScoringPolicy.policy_id == ScoringPolicyWeight.policy_id)
            .where(ScoringPolicy.is_active)
        )
        rows = result.all()
        if not rows:
            raise ConflictError(
                "No scoring policy is active. A System Administrator must configure "
                "the weighting before rankings can be generated."
            )
        weights = {CriterionKey(r.criterion_key): r.weight for r in rows}
        return weights, rows[0].policy_id

    async def run_and_persist(self, programme_id: int, actor_user_id: int) -> PredictionRunRead:
        """Generate a ranking and persist it (FR-06).

        Marks any prior run superseded rather than deleting it: what the system
        recommended, and when, is part of the audit record. An officer must be able to
        explain a decision taken against a ranking that has since been regenerated.

        Args:
            programme_id: The programme to staff.
            actor_user_id: Who requested the run.

        Returns:
            The persisted run.

        Raises:
            BusinessRuleViolation: If requirements are undefined (FR-05).
        """
        started = time.perf_counter()
        programme = await self.build_requirements(programme_id)
        weights, policy_id = await self.active_weights()
        facts, prior = await self._fetch_facts(programme)

        result = generate_prediction(
            programme, facts, weights, today=self._clock.now().date(), prior_mean=prior
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        # NFR-01 allows ten seconds. Warning at three surfaces degradation long before
        # it breaches, while there is still time to act on it.
        if elapsed_ms > self._settings.prediction_slow_warning_ms:
            logger.warning(
                "prediction_run_slow",
                programme_id=programme_id,
                elapsed_ms=elapsed_ms,
                candidate_pool_size=result.candidate_pool_size,
                threshold_ms=self._settings.prediction_slow_warning_ms,
            )

        await self._session.execute(
            update(PredictionRun)
            .where(
                PredictionRun.programme_id == programme_id,
                PredictionRun.is_superseded.is_(False),
            )
            .values(is_superseded=True)
        )

        run = PredictionRun(
            programme_id=programme_id,
            policy_id=policy_id,
            weights_snapshot={k.value: float(v) for k, v in weights.items()},
            weights_are_policy_default=True,
            candidate_pool_size=result.candidate_pool_size,
            excluded_count=result.excluded_count,
            ranked_count=result.ranked_count,
            elapsed_ms=elapsed_ms,
            is_superseded=False,
            generated_by_user_id=actor_user_id,
            generated_at=self._clock.now(),
        )
        self._session.add(run)
        await self._session.flush()

        # Bulk inserts: 700 ranked candidates and 100 exclusions as two statements,
        # not 800 individual adds.
        if result.predictions:
            self._session.add_all(
                [
                    Prediction(
                        run_id=run.run_id,
                        programme_id=programme_id,
                        trainer_id=candidate.facts.trainer_id,
                        prediction_score=candidate.total,
                        confidence_level=Decimal(candidate.confidence_level),
                        confidence_band=candidate.confidence_band.value,
                        rank_position=candidate.rank_position,
                        breakdown=[c.to_json() for c in candidate.breakdown],
                        rationale=candidate.rationale,
                        counterfactual=candidate.counterfactual,
                        generated_at=run.generated_at,
                    )
                    for candidate in result.predictions
                ]
            )
        if result.exclusions:
            self._session.add_all(
                [
                    PredictionExclusion(
                        run_id=run.run_id,
                        trainer_id=exclusion.trainer_id,
                        reason=exclusion.reason.value,
                        reason_detail=exclusion.reason_detail,
                        business_rule=exclusion.business_rule.value,
                        created_at=run.generated_at,
                    )
                    for exclusion in result.exclusions
                ]
            )
        await self._session.flush()

        entity = await self._session.get(TrainingProgramme, programme_id)
        if entity is not None:
            if entity.status in (
                ProgrammeStatus.DRAFT,
                ProgrammeStatus.REQUIREMENTS_SET,
                ProgrammeStatus.PREDICTED,
            ):
                entity.status = ProgrammeStatus.PREDICTED
            entity.requirements_changed_since_prediction = False
        await self._session.flush()

        await self._audit.record(
            AuditAction.PREDICTION_GENERATED,
            entity_type="PREDICTION_RUN",
            entity_id=programme_id,
            after={"run_id": run.run_id, "elapsed_ms": elapsed_ms},
            detail=(
                f"Ranked {result.ranked_count}, excluded {result.excluded_count}, "
                f"in {elapsed_ms / 1000:.1f}s."
            ),
        )
        return await self.get_run(run.run_id)

    async def simulate(
        self, programme_id: int, override: dict[CriterionKey, Decimal], actor_user_id: int
    ) -> tuple[PredictionRunRead, list[RankDelta]]:
        """Run the engine with override weights, persisting nothing (§5.8).

        Identical code path to :meth:`run_and_persist` — only the caller differs. The
        `WEIGHTS_SIMULATED` audit entry is the sole write, because who explored which
        weightings before approving is itself part of the decision record.

        Args:
            programme_id: The programme.
            override: Weights to use instead of the active policy.
            actor_user_id: Who simulated.

        Returns:
            The unpersisted run and the rank movements against the persisted one.
        """
        started = time.perf_counter()
        programme = await self.build_requirements(programme_id)
        facts, prior = await self._fetch_facts(programme)

        result = generate_prediction(
            programme, facts, override, today=self._clock.now().date(), prior_mean=prior
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        previous_ranks = await self._current_ranks(programme_id)
        deltas = self._rank_deltas(result, previous_ranks)

        await self._audit.record(
            AuditAction.WEIGHTS_SIMULATED,
            entity_type="TRAINING_PROGRAMME",
            entity_id=programme_id,
            after={k.value: float(v) for k, v in override.items()},
            detail=(
                f'Simulated weighting on "{programme.title}"; '
                f"{sum(1 for d in deltas if d.movement)} candidates changed rank."
            ),
        )

        view = self._to_view(
            result,
            programme_title=programme.title,
            run_id=None,
            generated_at=self._clock.now(),
            generated_by_name=None,
            elapsed_ms=elapsed_ms,
            weights_are_policy_default=False,
            trainer_lookup=await self._trainer_lookup(
                [c.facts.trainer_id for c in result.predictions]
            ),
        )
        _ = actor_user_id
        return view, deltas

    async def preview(self, programme_id: int) -> EligibilityPreview:
        """Run the gates only and return counts (§6.4).

        Args:
            programme_id: The programme.

        Returns:
            Eligible and total counts with a per-reason breakdown.
        """
        programme = await self.build_requirements(programme_id)
        facts, _prior = await self._fetch_facts(programme)
        return preview_eligibility(programme, facts)

    async def _current_ranks(self, programme_id: int) -> dict[int, int]:
        """Return trainer id to rank from the current persisted run."""
        result = await self._session.execute(
            select(Prediction.trainer_id, Prediction.rank_position)
            .join(PredictionRun, PredictionRun.run_id == Prediction.run_id)
            .where(
                PredictionRun.programme_id == programme_id,
                PredictionRun.is_superseded.is_(False),
            )
        )
        return {row.trainer_id: row.rank_position for row in result.all()}

    def _rank_deltas(
        self, result: PredictionRunResult, previous: dict[int, int]
    ) -> list[RankDelta]:
        """Compute rank movements between a simulation and the persisted run.

        Only the top fifty are returned. The Weight Studio shows movement to help an
        administrator judge whether a weighting change is material; a trainer moving
        from 431st to 428th is not information, it is noise.

        Args:
            result: The simulated run.
            previous: Trainer id to previous rank.

        Returns:
            Movements, largest first.
        """
        deltas: list[RankDelta] = []
        for candidate in result.predictions[:50]:
            trainer_id = candidate.facts.trainer_id
            before = previous.get(trainer_id)
            movement = (before - candidate.rank_position) if before is not None else 0
            deltas.append(
                RankDelta(
                    trainer_id=trainer_id,
                    trainer_name=candidate.facts.full_name,
                    previous_rank=before,
                    new_rank=candidate.rank_position,
                    movement=movement,
                )
            )
        deltas.sort(key=lambda d: abs(d.movement), reverse=True)
        return deltas

    async def _trainer_lookup(self, trainer_ids: list[int]) -> dict[int, tuple[str, str, str, str]]:
        """Load display details for a set of trainers in one query.

        Args:
            trainer_ids: Which trainers.

        Returns:
            Trainer id to ``(full_name, rank_code, force_number, station)``.
        """
        if not trainer_ids:
            return {}
        from app.models.reference import PoliceRank, Station

        result = await self._session.execute(
            select(
                Trainer.trainer_id,
                User.full_name,
                PoliceRank.code,
                Trainer.force_number,
                Station.name,
            )
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .join(Station, Station.station_id == Trainer.station_id)
            .where(Trainer.trainer_id.in_(trainer_ids))
        )
        return {r[0]: (r[1], r[2], r[3], r[4]) for r in result.all()}

    def _to_view(
        self,
        result: PredictionRunResult,
        *,
        programme_title: str,
        run_id: int | None,
        generated_at: object,
        generated_by_name: str | None,
        elapsed_ms: int,
        weights_are_policy_default: bool,
        trainer_lookup: dict[int, tuple[str, str, str, str]],
    ) -> PredictionRunRead:
        """Render an engine result as the API response shape.

        Args:
            result: The engine output.
            programme_title: For display.
            run_id: None for a simulation.
            generated_at: When.
            generated_by_name: Who, if persisted.
            elapsed_ms: Measured duration.
            weights_are_policy_default: False for a simulation.
            trainer_lookup: Display details.

        Returns:
            The response payload.
        """
        predictions = []
        for candidate in result.predictions:
            name, rank, force, station = trainer_lookup.get(
                candidate.facts.trainer_id,
                (
                    candidate.facts.full_name,
                    candidate.facts.rank_code,
                    candidate.facts.force_number,
                    candidate.facts.station_name,
                ),
            )
            predictions.append(
                PredictionRead(
                    prediction_id=None,
                    programme_id=result.programme_id,
                    trainer_id=candidate.facts.trainer_id,
                    trainer_name=name,
                    trainer_rank=rank,
                    force_number=force,
                    station=station,
                    prediction_score=candidate.total,
                    confidence_level=candidate.confidence_level,
                    confidence_band=candidate.confidence_band.value,
                    rank_position=candidate.rank_position,
                    breakdown=[
                        CriterionScoreRead(
                            key=c.key.value,
                            label=c.label,
                            weight=c.weight,
                            raw_value=c.raw_value,
                            normalized=c.normalized,
                            contribution=c.contribution,
                            explanation=c.explanation,
                            data_quality=c.data_quality.value,
                        )
                        for c in candidate.breakdown
                    ],
                    rationale=candidate.rationale,
                    counterfactual=candidate.counterfactual,
                )
            )

        return PredictionRunRead(
            run_id=run_id,
            programme_id=result.programme_id,
            programme_title=programme_title,
            generated_at=generated_at,  # type: ignore[arg-type]
            generated_by_name=generated_by_name,
            candidate_pool_size=result.candidate_pool_size,
            excluded_count=result.excluded_count,
            ranked_count=result.ranked_count,
            elapsed_ms=elapsed_ms,
            weights={k.value: float(v) for k, v in result.weights.items()},
            weights_are_policy_default=weights_are_policy_default,
            prior_mean=result.prior_mean,
            predictions=predictions,
            excluded=[
                ExclusionRead(
                    trainer_id=e.trainer_id,
                    full_name=e.full_name,
                    police_rank=e.rank_code,
                    force_number=e.force_number,
                    reason=e.reason.value,
                    reason_detail=e.reason_detail,
                    business_rule=e.business_rule.value,
                )
                for e in result.exclusions
            ],
        )

    async def get_run(self, run_id: int, *, limit: int | None = None) -> PredictionRunRead:
        """Load a persisted run.

        **Always ordered by `rank_position` ascending** (BR-05). There is no sort
        parameter: letting a client re-sort a ranked list would let the interface show
        a different recommendation from the one recorded.

        Args:
            run_id: Primary key.
            limit: Optionally cap the number of ranked rows returned.

        Returns:
            The run.

        Raises:
            NotFoundError: If it does not exist.
        """
        from app.models.reference import PoliceRank, Station

        header = await self._session.execute(
            select(
                PredictionRun.run_id,
                PredictionRun.programme_id,
                TrainingProgramme.title.label("programme_title"),
                PredictionRun.generated_at,
                User.full_name.label("generated_by_name"),
                PredictionRun.candidate_pool_size,
                PredictionRun.excluded_count,
                PredictionRun.ranked_count,
                PredictionRun.elapsed_ms,
                PredictionRun.weights_snapshot,
                PredictionRun.weights_are_policy_default,
                PredictionRun.is_superseded,
            )
            .join(
                TrainingProgramme,
                TrainingProgramme.programme_id == PredictionRun.programme_id,
            )
            .join(User, User.user_id == PredictionRun.generated_by_user_id)
            .where(PredictionRun.run_id == run_id)
        )
        row = header.one_or_none()
        if row is None:
            raise NotFoundError("That prediction run could not be found.")

        query = (
            select(
                Prediction.prediction_id,
                Prediction.programme_id,
                Prediction.trainer_id,
                User.full_name.label("trainer_name"),
                PoliceRank.code.label("trainer_rank"),
                Trainer.force_number,
                Station.name.label("station"),
                Prediction.prediction_score,
                Prediction.confidence_level,
                Prediction.confidence_band,
                Prediction.rank_position,
                Prediction.breakdown,
                Prediction.rationale,
                Prediction.counterfactual,
                Prediction.generated_at,
            )
            .join(Trainer, Trainer.trainer_id == Prediction.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .join(Station, Station.station_id == Trainer.station_id)
            .where(Prediction.run_id == run_id)
            .order_by(Prediction.rank_position)
        )
        if limit is not None:
            query = query.limit(limit)
        prediction_rows = await self._session.execute(query)

        return PredictionRunRead(
            run_id=row.run_id,
            programme_id=row.programme_id,
            programme_title=row.programme_title,
            generated_at=row.generated_at,
            generated_by_name=row.generated_by_name,
            candidate_pool_size=row.candidate_pool_size,
            excluded_count=row.excluded_count,
            ranked_count=row.ranked_count,
            elapsed_ms=row.elapsed_ms,
            weights=row.weights_snapshot,
            weights_are_policy_default=row.weights_are_policy_default,
            is_superseded=row.is_superseded,
            predictions=[
                PredictionRead(
                    prediction_id=p.prediction_id,
                    programme_id=p.programme_id,
                    trainer_id=p.trainer_id,
                    trainer_name=p.trainer_name,
                    trainer_rank=p.trainer_rank,
                    force_number=p.force_number,
                    station=p.station,
                    prediction_score=p.prediction_score,
                    confidence_level=int(p.confidence_level),
                    confidence_band=p.confidence_band,
                    rank_position=p.rank_position,
                    breakdown=[CriterionScoreRead.model_validate(c) for c in p.breakdown],
                    rationale=p.rationale,
                    counterfactual=p.counterfactual,
                    generated_at=p.generated_at,
                )
                for p in prediction_rows.all()
            ],
        )

    async def latest_run_for(self, programme_id: int) -> PredictionRunRead:
        """Return the current, non-superseded run for a programme.

        Args:
            programme_id: Primary key.

        Returns:
            The run.

        Raises:
            NotFoundError: If no ranking has been generated yet.
        """
        result = await self._session.execute(
            select(PredictionRun.run_id)
            .where(
                PredictionRun.programme_id == programme_id,
                PredictionRun.is_superseded.is_(False),
            )
            .order_by(PredictionRun.generated_at.desc())
            .limit(1)
        )
        run_id = result.scalar_one_or_none()
        if run_id is None:
            raise NotFoundError("No ranking has been generated for this programme yet.")
        return await self.get_run(run_id)

    async def exclusions_for(self, run_id: int) -> list[ExclusionGroup]:
        """Return a run's Exclusion Ledger, grouped by reason (§6.5).

        Args:
            run_id: Primary key.

        Returns:
            Groups, largest first.
        """
        from app.models.reference import PoliceRank

        result = await self._session.execute(
            select(
                PredictionExclusion.trainer_id,
                User.full_name,
                PoliceRank.code.label("police_rank"),
                Trainer.force_number,
                PredictionExclusion.reason,
                PredictionExclusion.reason_detail,
                PredictionExclusion.business_rule,
            )
            .join(Trainer, Trainer.trainer_id == PredictionExclusion.trainer_id)
            .join(User, User.user_id == Trainer.user_id)
            .join(PoliceRank, PoliceRank.rank_id == Trainer.rank_id)
            .where(PredictionExclusion.run_id == run_id)
            .order_by(PredictionExclusion.reason, User.full_name)
        )
        grouped: dict[str, list[ExclusionRead]] = {}
        rules: dict[str, str] = {}
        for row in result.all():
            grouped.setdefault(row.reason, []).append(ExclusionRead.model_validate(row))
            rules[row.reason] = row.business_rule

        return sorted(
            (
                ExclusionGroup(
                    reason=reason,
                    business_rule=rules[reason],
                    count=len(trainers),
                    trainers=trainers,
                )
                for reason, trainers in grouped.items()
            ),
            key=lambda g: g.count,
            reverse=True,
        )
