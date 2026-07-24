"""Populate the database with the deterministic demo dataset (§7).

Run with ``python -m scripts.seed``. Idempotent: reference data is upserted by
natural key, and transactional data is wiped and rebuilt, so running it twice leaves
exactly the same rows rather than duplicating them.

Structure mirrors the schema's dependency order — reference tables, then identity,
then the trainer domain, then programmes, then the prediction and allocation records
the engine produced.
"""

from __future__ import annotations

import asyncio
import secrets
import sys
import time
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from argon2 import PasswordHasher
from sqlalchemy import Row, delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import DEMO_PASSWORD
from app.db.session import engine, session_scope
from app.models import (
    Allocation,
    AuditLog,
    Directorate,
    Institution,
    Notification,
    PerformanceEvaluation,
    PoliceRank,
    Prediction,
    PredictionExclusion,
    PredictionRun,
    ProficiencyLevel,
    QualificationLevel,
    Region,
    Role,
    ScoringPolicy,
    ScoringPolicyWeight,
    SpecializationArea,
    Station,
    Trainer,
    TrainerQualification,
    TrainerSpecialization,
    TrainerUnavailability,
    TrainingCategory,
    TrainingProgramme,
    User,
)
from data.seed_source import reference_data as ref
from data.seed_source.generator import Dataset, assert_fixtures, generate


def _pairs[K, V](rows: Sequence[Row[tuple[K, V]]]) -> dict[K, V]:
    """Turn a two-column result into a lookup dictionary.

    ``dict(result.all())`` works at runtime but defeats the type checker: a
    :class:`~sqlalchemy.Row` is a sequence, not a two-tuple, so mypy infers
    ``dict[Never, Never]``. This preserves the column types, which matters because
    every one of these dictionaries is used to resolve a foreign key.

    Args:
        rows: Result rows of exactly two columns.

    Returns:
        A mapping from the first column to the second.
    """
    return {row[0]: row[1] for row in rows}


#: Transactional tables, in the order they must be emptied (children first).
TRANSACTIONAL_TABLES: tuple[str, ...] = (
    "notifications",
    "audit_logs",
    "performance_evaluations",
    "allocations",
    "prediction_exclusions",
    "predictions",
    "prediction_runs",
    "training_programmes",
    "trainer_unavailability",
    "trainer_specializations",
    "trainer_qualifications",
    "trainers",
    "refresh_tokens",
)


def _hasher() -> PasswordHasher:
    """Build the Argon2id hasher from configured parameters.

    Phase 2's verifier must construct this identically, or every seeded account
    fails to authenticate. That is why the parameters live in settings rather than
    being written inline here.
    """
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        hash_len=settings.argon2_hash_length,
        salt_len=settings.argon2_salt_length,
    )


async def _upsert_reference(session: AsyncSession) -> None:
    """Insert reference rows that are missing, leaving existing ones untouched.

    Matched on natural key — a rank's ``code``, a station's ``(name, region)`` — not
    on the surrogate primary key, so re-running does not renumber anything that other
    tables already point at.
    """

    async def existing(model: Any, column: Any) -> set[Any]:
        rows = await session.execute(select(column))
        return set(rows.scalars().all())

    have = await existing(Role, Role.name)
    session.add_all(
        [
            Role(
                name=r.name, display_name=r.display_name, description=r.description, is_system=True
            )
            for r in ref.ROLES
            if r.name not in have
        ]
    )

    have = await existing(PoliceRank, PoliceRank.code)
    session.add_all(
        [
            PoliceRank(
                code=r.code,
                full_name=r.full_name,
                management_level=r.level,
                seniority_order=r.order,
                typical_appointments=r.appointments,
            )
            for r in ref.POLICE_RANKS
            if r.code not in have
        ]
    )

    have = await existing(Directorate, Directorate.name)
    session.add_all(
        [
            Directorate(
                name=d.name,
                abbreviation=d.abbreviation,
                is_training_authority=d.is_training_authority,
            )
            for d in ref.DIRECTORATES
            if d.name not in have
        ]
    )

    have = await existing(Region, Region.name)
    session.add_all(
        [
            Region(name=r.name, headquarters=r.headquarters)
            for r in ref.REGIONS
            if r.name not in have
        ]
    )

    have = await existing(TrainingCategory, TrainingCategory.name)
    session.add_all(
        [
            TrainingCategory(name=c.name, description=c.description)
            for c in ref.TRAINING_CATEGORIES
            if c.name not in have
        ]
    )

    have = await existing(Institution, Institution.name)
    session.add_all(
        [
            Institution(name=i.name, institution_type=i.institution_type, country=i.country)
            for i in ref.INSTITUTIONS
            if i.name not in have
        ]
    )

    have = await existing(QualificationLevel, QualificationLevel.code)
    session.add_all(
        [
            QualificationLevel(code=q.code, name=q.name, rank_order=q.order, score_value=q.score)
            for q in ref.QUALIFICATION_LEVELS
            if q.code not in have
        ]
    )

    have = await existing(ProficiencyLevel, ProficiencyLevel.code)
    session.add_all(
        [
            ProficiencyLevel(code=p.code, name=p.name, rank_order=p.order, score_value=p.score)
            for p in ref.PROFICIENCY_LEVELS
            if p.code not in have
        ]
    )
    await session.flush()

    # Stations and specialisation areas depend on regions and directorates.
    region_ids = _pairs((await session.execute(select(Region.name, Region.region_id))).all())
    have = await existing(Station, Station.name)
    session.add_all(
        [
            Station(
                name=s.name,
                region_id=region_ids[s.region],
                district=s.district,
                station_type=s.station_type,
                is_active=True,
            )
            for s in ref.STATIONS
            if s.name not in have
        ]
    )

    directorate_ids = _pairs(
        (await session.execute(select(Directorate.name, Directorate.directorate_id))).all()
    )
    have = await existing(SpecializationArea, SpecializationArea.name)
    session.add_all(
        [
            SpecializationArea(
                name=a.name,
                description=a.description,
                directorate_id=directorate_ids.get(a.directorate),
                discipline_group=a.discipline_group,
                is_active=True,
            )
            for a in ref.SPECIALIZATION_AREAS
            if a.name not in have
        ]
    )
    await session.flush()


async def _upsert_scoring_policy(session: AsyncSession) -> int:
    """Ensure policy version 1 exists and is active. Returns its id."""
    existing = await session.execute(select(ScoringPolicy).where(ScoringPolicy.version == 1))
    policy = existing.scalar_one_or_none()
    if policy is None:
        policy = ScoringPolicy(
            version=1,
            name="Standard policy",
            is_active=True,
            notes="Adopted at go-live. The balanced weighting approved as force policy.",
        )
        session.add(policy)
        await session.flush()
        session.add_all(
            [
                ScoringPolicyWeight(
                    policy_id=policy.policy_id,
                    criterion_key=w.key,
                    display_label=w.label,
                    weight=w.weight,
                    description=w.description,
                    sort_order=w.sort_order,
                )
                for w in ref.STANDARD_POLICY_WEIGHTS
            ]
        )
        await session.flush()
    return policy.policy_id


async def _clear_transactional(session: AsyncSession) -> None:
    """Empty every transactional table, leaving reference data and policy intact.

    ``TRUNCATE`` rather than ``DELETE``: it is set-based, resets the identity
    sequences, and — relevant here — is not intercepted by the audit-immutability
    trigger, which guards row-level ``UPDATE`` and ``DELETE`` only. That distinction
    is deliberate and documented in ADR-0005: FR-13 protects the trail from *users*,
    while a developer resetting their own machine holds table ownership and is
    outside that threat model.
    """
    tables = ", ".join(TRANSACTIONAL_TABLES)
    await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    # Non-demo users are removed; the four demo accounts survive a reset by design.
    await session.execute(delete(User).where(User.username.notin_(list(ref_demo_usernames()))))
    for sequence in ("registry_req_seq", "registry_all_seq", "registry_evl_seq"):
        await session.execute(text(f"ALTER SEQUENCE {sequence} RESTART"))


def ref_demo_usernames() -> tuple[str, ...]:
    """Return the four demo usernames, which survive a reset."""
    return ("admin.training", "officer.training", "trainer", "sysadmin")


async def _registry_numbers(session: AsyncSession, family: str, count: int) -> list[str]:
    """Draw ``count`` registry numbers from the database's own sequence.

    Uses ``next_registry_number()`` rather than formatting strings in Python, so the
    seeded numbers come from the same concurrency-safe source Phase 2 will use and
    the sequence is left at the correct position afterwards.
    """
    rows = await session.execute(
        text("SELECT next_registry_number(:family) FROM generate_series(1, :count)"),
        {"family": family, "count": count},
    )
    return list(rows.scalars().all())


async def seed(dataset: Dataset) -> dict[str, int]:
    """Write the generated dataset to the database.

    Args:
        dataset: The in-memory dataset from the generator.

    Returns:
        Row counts per entity, for the console summary.
    """
    counts: dict[str, int] = {}
    hasher = _hasher()

    # The four demo accounts get real Argon2id hashes of the documented password.
    # The other 850 share one hash of a random secret that is discarded — they are
    # data, not credentials, and nobody can sign into them. Hashing each of them
    # individually would cost 220 seconds (measured) and buy nothing; giving them all
    # a *known* password would be worse than giving them none.
    demo_hash = hasher.hash(DEMO_PASSWORD)
    unusable_hash = hasher.hash(secrets.token_urlsafe(32))

    async with session_scope() as session:
        await _upsert_reference(session)
        policy_id = await _upsert_scoring_policy(session)
        await _clear_transactional(session)

        # --- Reference id lookups ------------------------------------------
        role_ids = _pairs((await session.execute(select(Role.name, Role.role_id))).all())
        rank_ids = _pairs(
            (await session.execute(select(PoliceRank.code, PoliceRank.rank_id))).all()
        )
        station_ids = _pairs(
            (await session.execute(select(Station.name, Station.station_id))).all()
        )
        directorate_ids = _pairs(
            (await session.execute(select(Directorate.name, Directorate.directorate_id))).all()
        )
        category_ids = _pairs(
            (
                await session.execute(select(TrainingCategory.name, TrainingCategory.category_id))
            ).all()
        )
        area_ids = _pairs(
            (
                await session.execute(
                    select(SpecializationArea.name, SpecializationArea.specialization_area_id)
                )
            ).all()
        )
        institution_ids = _pairs(
            (await session.execute(select(Institution.name, Institution.institution_id))).all()
        )
        qual_level_ids = _pairs(
            (
                await session.execute(select(QualificationLevel.code, QualificationLevel.level_id))
            ).all()
        )
        prof_level_ids = _pairs(
            (await session.execute(select(ProficiencyLevel.code, ProficiencyLevel.level_id))).all()
        )

        # --- Users ---------------------------------------------------------
        # The four demo accounts may already exist (they survive a reset), so they
        # are updated in place rather than re-inserted.
        existing_demo = _pairs(
            (
                await session.execute(
                    select(User.username, User.user_id).where(
                        User.username.in_(list(ref_demo_usernames()))
                    )
                )
            ).all()
        )
        user_rows: list[dict[str, Any]] = []
        for user in dataset.users:
            if user.username in existing_demo:
                continue
            user_rows.append(
                {
                    "username": user.username,
                    "email": user.email,
                    "password_hash": demo_hash if user.is_demo else unusable_hash,
                    "full_name": user.full_name,
                    "role_id": role_ids[user.role_name],
                    "rank_id": rank_ids.get(user.rank_code),
                    "account_status": user.account_status,
                    "failed_login_count": 0,
                    "must_change_password": False,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                    "updated_at": user.created_at,
                }
            )
        if user_rows:
            await session.execute(insert(User), user_rows)
        await session.flush()

        user_ids = _pairs((await session.execute(select(User.username, User.user_id))).all())
        # Map generator index -> database id.
        uid = {u.index: user_ids[u.username] for u in dataset.users}
        counts["users"] = len(dataset.users)

        # --- Trainers ------------------------------------------------------
        trainer_rows = [
            {
                "user_id": uid[t.user_index],
                "force_number": t.force_number,
                "rank_id": rank_ids[t.rank_code],
                "station_id": station_ids[t.station_name],
                "directorate_id": directorate_ids[t.directorate_name],
                "date_of_enlistment": t.date_of_enlistment,
                "years_experience": t.years_experience,
                "availability_status": t.availability_status,
                "contact_number": t.contact_number,
                "bio": t.bio,
                "searchable_name": t.full_name,
                "profile_completeness": t.profile_completeness,
            }
            for t in dataset.trainers
        ]
        await session.execute(insert(Trainer), trainer_rows)
        await session.flush()
        trainer_ids = _pairs(
            (await session.execute(select(Trainer.force_number, Trainer.trainer_id))).all()
        )
        tid = {t.index: trainer_ids[t.force_number] for t in dataset.trainers}
        counts["trainers"] = len(dataset.trainers)

        # --- Qualifications and specialisations -----------------------------
        qual_rows: list[dict[str, Any]] = []
        spec_rows: list[dict[str, Any]] = []
        for trainer in dataset.trainers:
            for (name, level, institution), year in zip(
                trainer.qualifications, trainer.qualification_years, strict=False
            ):
                qual_rows.append(
                    {
                        "trainer_id": tid[trainer.index],
                        "qualification_name": name,
                        "level_id": qual_level_ids[level],
                        "institution_id": institution_ids[institution],
                        "year_obtained": year,
                    }
                )
            for area, level, years_in_area in trainer.specializations:
                spec_rows.append(
                    {
                        "trainer_id": tid[trainer.index],
                        "specialization_area_id": area_ids[area],
                        "proficiency_level_id": prof_level_ids[level],
                        "years_in_area": years_in_area,
                    }
                )
        await session.execute(insert(TrainerQualification), qual_rows)
        await session.execute(insert(TrainerSpecialization), spec_rows)
        counts["trainer_qualifications"] = len(qual_rows)
        counts["trainer_specializations"] = len(spec_rows)

        if dataset.unavailability:
            await session.execute(
                insert(TrainerUnavailability),
                [
                    {
                        "trainer_id": tid[u.trainer_index],
                        "start_date": u.start_date,
                        "end_date": u.end_date,
                        "reason": u.reason,
                        "category": u.category,
                        "recorded_by_user_id": uid[0],
                    }
                    for u in dataset.unavailability
                ],
            )
        counts["trainer_unavailability"] = len(dataset.unavailability)

        # --- Programmes -----------------------------------------------------
        registry_req = await _registry_numbers(session, "REQ", len(dataset.programmes))
        programme_rows = [
            {
                "registry_number": registry_req[i],
                "title": p.title,
                "category_id": category_ids[p.category_name],
                "required_specialization_area_id": (
                    area_ids[p.required_area_name] if p.required_area_name else None
                ),
                "minimum_experience": p.minimum_experience,
                "minimum_qualification_level_id": (
                    qual_level_ids[p.minimum_qualification_code]
                    if p.minimum_qualification_code
                    else None
                ),
                "start_date": p.start_date,
                "end_date": p.end_date,
                "station_id": station_ids[p.station_name],
                "expected_participants": p.expected_participants,
                "status": p.status,
                "requirements_set_at": p.requirements_set_at,
                "requirements_changed_since_prediction": False,
                "created_by_user_id": uid[p.created_by_user_index],
                "created_at": p.created_at,
                "updated_at": p.created_at,
            }
            for i, p in enumerate(dataset.programmes)
        ]
        await session.execute(insert(TrainingProgramme), programme_rows)
        await session.flush()
        programme_ids = _pairs(
            (
                await session.execute(
                    select(TrainingProgramme.registry_number, TrainingProgramme.programme_id)
                )
            ).all()
        )
        pid = {p.index: programme_ids[registry_req[i]] for i, p in enumerate(dataset.programmes)}
        counts["training_programmes"] = len(dataset.programmes)

        # --- Runs, predictions, exclusions ----------------------------------
        weights_snapshot = {w.key: float(w.weight) for w in ref.STANDARD_POLICY_WEIGHTS}
        run_rows = [
            {
                "programme_id": pid[r.programme_index],
                "policy_id": policy_id,
                "weights_snapshot": weights_snapshot,
                "weights_are_policy_default": True,
                "candidate_pool_size": r.candidate_pool_size,
                "excluded_count": r.excluded_count,
                "ranked_count": r.ranked_count,
                "elapsed_ms": r.elapsed_ms,
                "is_superseded": False,
                "generated_by_user_id": uid[r.generated_by_user_index],
                "generated_at": r.generated_at,
                "created_at": r.generated_at,
                "updated_at": r.generated_at,
            }
            for r in dataset.runs
        ]
        await session.execute(insert(PredictionRun), run_rows)
        await session.flush()
        run_id_by_programme = _pairs(
            (await session.execute(select(PredictionRun.programme_id, PredictionRun.run_id))).all()
        )
        rid = {r.programme_index: run_id_by_programme[pid[r.programme_index]] for r in dataset.runs}
        counts["prediction_runs"] = len(dataset.runs)

        prediction_rows: list[dict[str, Any]] = []
        exclusion_rows: list[dict[str, Any]] = []
        for run in dataset.runs:
            run_db_id = rid[run.programme_index]
            programme_db_id = pid[run.programme_index]
            for prediction in run.predictions:
                prediction_rows.append(
                    {
                        "run_id": run_db_id,
                        "programme_id": programme_db_id,
                        "trainer_id": tid[prediction.trainer_index],
                        "prediction_score": prediction.prediction_score,
                        "confidence_level": Decimal(prediction.confidence_level),
                        "confidence_band": prediction.confidence_band,
                        "rank_position": prediction.rank_position,
                        "breakdown": prediction.breakdown,
                        "rationale": prediction.rationale,
                        "counterfactual": prediction.counterfactual,
                        "generated_at": run.generated_at,
                    }
                )
            for exclusion in run.exclusions:
                exclusion_rows.append(
                    {
                        "run_id": run_db_id,
                        "trainer_id": tid[exclusion.trainer_index],
                        "reason": exclusion.reason,
                        "reason_detail": exclusion.reason_detail,
                        "business_rule": exclusion.business_rule,
                        "created_at": run.generated_at,
                    }
                )
        await session.execute(insert(Prediction), prediction_rows)
        await session.execute(insert(PredictionExclusion), exclusion_rows)
        await session.flush()
        counts["predictions"] = len(prediction_rows)
        counts["prediction_exclusions"] = len(exclusion_rows)

        # --- Allocations ----------------------------------------------------
        # Only the allocated predictions need their ids looked up, not all 7,000.
        wanted = {(rid[a.programme_index], tid[a.trainer_index]) for a in dataset.allocations}
        prediction_lookup = {
            (r, t): p
            for r, t, p in (
                await session.execute(
                    select(
                        Prediction.run_id, Prediction.trainer_id, Prediction.prediction_id
                    ).where(Prediction.run_id.in_({r for r, _ in wanted}))
                )
            ).all()
            if (r, t) in wanted
        }

        registry_all = await _registry_numbers(session, "ALL", len(dataset.allocations))
        allocation_rows = [
            {
                "registry_number": registry_all[i],
                "prediction_id": prediction_lookup[(rid[a.programme_index], tid[a.trainer_index])],
                "programme_id": pid[a.programme_index],
                "trainer_id": tid[a.trainer_index],
                "approved_by_user_id": uid[a.approved_by_user_index],
                "status": a.status,
                "approval_date": a.approval_date,
                "remarks": a.remarks,
                "frozen_score": a.frozen_score,
                "frozen_rank_position": a.frozen_rank_position,
                "frozen_breakdown": a.frozen_breakdown,
                "frozen_weights": a.frozen_weights,
                "frozen_rationale": a.frozen_rationale,
                "weights_were_simulated": a.weights_were_simulated,
                "decline_reason": a.decline_reason,
                "declined_at": a.declined_at,
                "responded_at": a.responded_at,
                "created_at": a.approval_date,
                "updated_at": a.approval_date,
            }
            for i, a in enumerate(dataset.allocations)
        ]
        await session.execute(insert(Allocation), allocation_rows)
        await session.flush()
        allocation_ids = _pairs(
            (
                await session.execute(select(Allocation.registry_number, Allocation.allocation_id))
            ).all()
        )
        aid = {a.index: allocation_ids[registry_all[i]] for i, a in enumerate(dataset.allocations)}
        counts["allocations"] = len(dataset.allocations)

        # --- Evaluations ----------------------------------------------------
        registry_evl = await _registry_numbers(session, "EVL", len(dataset.evaluations))
        await session.execute(
            insert(PerformanceEvaluation),
            [
                {
                    "registry_number": registry_evl[i],
                    "allocation_id": aid[e.allocation_index],
                    "trainer_id": tid[e.trainer_index],
                    "programme_id": pid[e.programme_index],
                    "score_awarded": e.score_awarded,
                    "evaluator_comments": e.evaluator_comments,
                    "evaluated_by_user_id": uid[e.evaluated_by_user_index],
                    "evaluation_date": e.evaluation_date,
                }
                for i, e in enumerate(dataset.evaluations)
            ],
        )
        counts["performance_evaluations"] = len(dataset.evaluations)

        # --- Audit and notifications ----------------------------------------
        entity_id_for = {
            "TRAINING_PROGRAMME": pid,
            "PREDICTION_RUN": pid,
            "ALLOCATION": aid,
            "PERFORMANCE_EVALUATION": tid,
            "USER": uid,
        }
        await session.execute(
            insert(AuditLog),
            [
                {
                    "actor_user_id": uid.get(a.actor_user_index)
                    if a.actor_user_index is not None
                    else None,
                    "actor_role": a.actor_role,
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "entity_id": (
                        entity_id_for.get(a.entity_type, {}).get(a.entity_ref)
                        if a.entity_type and a.entity_ref is not None
                        else None
                    ),
                    "detail": a.detail,
                    "ip_address": a.ip_address,
                    "created_at": a.created_at,
                }
                for a in dataset.audit
            ],
        )
        counts["audit_logs"] = len(dataset.audit)

        await session.execute(
            insert(Notification),
            [
                {
                    "recipient_user_id": uid[n.recipient_user_index],
                    "message": n.message,
                    "type": n.type,
                    "link_to": n.link_to,
                    "status": n.status,
                    "delivery_status": n.delivery_status,
                    "sent_date": n.sent_date,
                    "read_at": n.read_at,
                    "created_at": n.sent_date,
                    "updated_at": n.sent_date,
                }
                for n in dataset.notifications
            ],
        )
        counts["notifications"] = len(dataset.notifications)

    return counts


async def main() -> int:
    """Generate, verify, and persist the dataset. Returns a process exit code."""
    settings = get_settings()
    started = time.perf_counter()

    print("TPS seed — Trainer Prediction System, Uganda Police Force")
    # Report the host actually connected to. With DATABASE_URL set (a managed database),
    # the five POSTGRES_* parts are unused, so printing them would say "localhost" while
    # writing to Supabase — precisely the confusion this line exists to avoid.
    print(f"  database : {settings.effective_db_host}  (ssl={settings.use_db_ssl})")
    print(f"  prng seed: {settings.seed_random_seed}")
    print()

    print("Generating dataset...")
    dataset = generate(settings.seed_random_seed)

    print("Verifying the eight narrative fixtures (§7.4)...")
    for line in assert_fixtures(dataset):
        print(f"  ✓ {line}")
    print()

    print("Writing to the database...")
    counts = await seed(dataset)
    elapsed = time.perf_counter() - started

    width = max(len(name) for name in counts)
    print()
    print("Rows written")
    print("-" * (width + 12))
    for name, count in counts.items():
        print(f"  {name:<{width}}  {count:>8,}")
    print("-" * (width + 12))
    print(f"  {'total':<{width}}  {sum(counts.values()):>8,}")
    print()
    print(f"Completed in {elapsed:.1f}s")
    print()
    print("Demo accounts — password for all four: " + DEMO_PASSWORD)
    print("  admin.training    Grace Nabirye     SSP  Training Administrator")
    print("  officer.training  Joseph Okello     ASP  Training Officer")
    print("  trainer           Sarah Mugisha     IP   Trainer")
    print("  sysadmin          Denis Byaruhanga  SP   System Administrator")
    print()
    print("Every other seeded account has no usable password by design and cannot be")
    print("signed into. They exist as data, not as credentials.")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


# Re-exported so `verify.py` can assert against the same list.
__all__ = ["TRANSACTIONAL_TABLES", "main", "seed"]
