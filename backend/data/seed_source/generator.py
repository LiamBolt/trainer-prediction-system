"""Deterministic generation of the TPS demo dataset (§7).

The system has no historical data, so the seed **is** the data. It must withstand a
Training Directorate officer reading it and recognising their own organisation.

**Determinism.** One :class:`random.Random` seeded with ``SEED_RANDOM_SEED`` is
threaded through every generator, and generation order is fixed. Reordering any loop
in this file changes the entire dataset. A demo that reshuffles itself is not a demo,
and a non-reproducible dataset cannot be reasoned about.

This differs from the frontend mocks, which use a mulberry32 PRNG. §7.1 mandates
``random.Random(20260722)``, so individual names and force numbers cannot match the
mocks byte-for-byte. What *is* matched exactly, because it is what §7.1 actually
requires, is the **volumes** and the **narrative fixtures** (§7.4) — measured from
the mock generator rather than taken from §7.1's stated figures, which are stale for
three of seven entities (conflict C3, ADR-0010).

This module produces plain dataclasses. Nothing here touches the database;
``scripts/seed.py`` owns persistence. That separation is what makes the fixture
assertions at the bottom of this file testable without a database.
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from app.core.constants import DEMO_PASSWORD
from app.models.enums import (
    AllocationStatus,
    AuditAction,
    AvailabilityStatus,
    DeliveryStatus,
    NotificationStatus,
    NotificationType,
    ProgrammeStatus,
    RoleName,
    UnavailabilityCategory,
)
from data.seed_source import reference_data as ref
from data.seed_source.scoring import (
    SeedEvaluation,
    SeedProgramme,
    SeedQualification,
    SeedSpecialization,
    SeedTrainer,
    build_counterfactual,
    build_rationale,
    run_prediction,
)

#: The dataset's "today". Fixed so that "starts in 24 days" means the same thing on
#: every run — a relative date computed from the wall clock would make the demo drift
#: out of its own narrative within a fortnight.
NOW: Final = datetime.date(2026, 7, 22)

TRAINER_COUNT: Final = 812
PROGRAMME_COUNT: Final = 46
STAFF_USER_COUNT: Final = 39
TARGET_AUDIT_ENTRIES: Final = 600
NOTIFICATION_COUNT: Final = 18

#: The featured programme's index. Ranked first so it is the first thing seen.
FEATURED_PROGRAMME_INDEX: Final = 0

DEFAULT_WEIGHTS: Final[dict[str, Decimal]] = {
    weight.key: weight.weight for weight in ref.STANDARD_POLICY_WEIGHTS
}


# --- Output dataclasses ----------------------------------------------------


@dataclass(slots=True)
class GenUser:
    """A user account awaiting persistence."""

    index: int
    username: str
    full_name: str
    email: str
    role_name: str
    rank_code: str
    station_name: str
    directorate_name: str
    account_status: str
    last_login_at: datetime.datetime | None
    created_at: datetime.datetime
    is_demo: bool = False


@dataclass(slots=True)
class GenTrainer:
    """A trainer awaiting persistence, paired with its scoring view."""

    index: int
    user_index: int
    force_number: str
    rank_code: str
    station_name: str
    directorate_name: str
    date_of_enlistment: datetime.date
    years_experience: int
    availability_status: str
    contact_number: str
    bio: str | None
    profile_completeness: int
    full_name: str
    qualifications: list[tuple[str, str, str]] = field(default_factory=list)
    """(qualification_name, level_code, institution_name)."""
    qualification_years: list[int] = field(default_factory=list)
    specializations: list[tuple[str, str, int | None]] = field(default_factory=list)
    """(area_name, proficiency_code, years_in_area)."""


@dataclass(slots=True)
class GenUnavailability:
    """A declared absence window."""

    trainer_index: int
    start_date: datetime.date
    end_date: datetime.date
    reason: str
    category: str


@dataclass(slots=True)
class GenProgramme:
    """A training programme awaiting persistence."""

    index: int
    title: str
    category_name: str
    required_area_name: str | None
    minimum_experience: int
    minimum_qualification_code: str | None
    start_date: datetime.date
    end_date: datetime.date
    station_name: str
    expected_participants: int
    status: str
    created_at: datetime.datetime
    requirements_set_at: datetime.datetime | None
    created_by_user_index: int


@dataclass(slots=True)
class GenPrediction:
    """One ranked candidate within a run."""

    trainer_index: int
    prediction_score: Decimal
    confidence_level: int
    confidence_band: str
    rank_position: int
    breakdown: list[dict[str, object]]
    rationale: str
    counterfactual: str | None


@dataclass(slots=True)
class GenExclusion:
    """One gated-out candidate within a run."""

    trainer_index: int
    reason: str
    reason_detail: str
    business_rule: str


@dataclass(slots=True)
class GenRun:
    """One prediction run."""

    programme_index: int
    generated_at: datetime.datetime
    candidate_pool_size: int
    excluded_count: int
    ranked_count: int
    elapsed_ms: int
    generated_by_user_index: int
    predictions: list[GenPrediction]
    exclusions: list[GenExclusion]


@dataclass(slots=True)
class GenAllocation:
    """An approved allocation, with its frozen decision snapshot."""

    index: int
    programme_index: int
    trainer_index: int
    run_index: int
    rank_position: int
    status: str
    approval_date: datetime.datetime
    remarks: str | None
    frozen_score: Decimal
    frozen_rank_position: int
    frozen_breakdown: list[dict[str, object]]
    frozen_weights: dict[str, float]
    frozen_rationale: str
    weights_were_simulated: bool
    decline_reason: str | None
    declined_at: datetime.datetime | None
    responded_at: datetime.datetime | None
    approved_by_user_index: int


@dataclass(slots=True)
class GenEvaluation:
    """A recorded performance evaluation."""

    allocation_index: int
    trainer_index: int
    programme_index: int
    score_awarded: Decimal
    evaluator_comments: str
    evaluation_date: datetime.date
    evaluated_by_user_index: int


@dataclass(slots=True)
class GenAudit:
    """An audit entry."""

    actor_user_index: int | None
    actor_role: str | None
    action: str
    entity_type: str | None
    entity_ref: int | None
    detail: str
    ip_address: str
    created_at: datetime.datetime


@dataclass(slots=True)
class GenNotification:
    """A notification."""

    recipient_user_index: int
    message: str
    type: str
    link_to: str | None
    status: str
    delivery_status: str
    sent_date: datetime.datetime
    read_at: datetime.datetime | None


@dataclass(slots=True)
class Dataset:
    """The complete generated dataset."""

    users: list[GenUser]
    trainers: list[GenTrainer]
    unavailability: list[GenUnavailability]
    programmes: list[GenProgramme]
    runs: list[GenRun]
    allocations: list[GenAllocation]
    evaluations: list[GenEvaluation]
    audit: list[GenAudit]
    notifications: list[GenNotification]
    demo_password: str = DEMO_PASSWORD


# --- Helpers ---------------------------------------------------------------

_POLICE_INSTITUTIONS: Final[frozenset[str]] = frozenset(
    inst.name for inst in ref.INSTITUTIONS if inst.institution_type == "POLICE"
)
_QUALIFICATION_ORDER: Final[dict[str, int]] = {
    level.code: level.order for level in ref.QUALIFICATION_LEVELS
}
_QUALIFICATION_SCORE: Final[dict[str, Decimal]] = {
    level.code: level.score for level in ref.QUALIFICATION_LEVELS
}
_PROFICIENCY_SCORE: Final[dict[str, Decimal]] = {
    level.code: level.score for level in ref.PROFICIENCY_LEVELS
}
_DISCIPLINE_GROUP: Final[dict[str, str]] = {
    area.name: area.discipline_group for area in ref.SPECIALIZATION_AREAS
}
_AREA_DIRECTORATE: Final[dict[str, str]] = {
    area.name: area.directorate for area in ref.SPECIALIZATION_AREAS
}


def _at(day: datetime.date, hour: int = 9, minute: int = 0) -> datetime.datetime:
    """Return a timezone-aware UTC datetime on a given date."""
    return datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=datetime.UTC)


def _weighted_choice(rng: random.Random, entries: tuple[tuple[str, int], ...]) -> str:
    """Pick one entry by integer weight."""
    population = [item for item, _ in entries]
    weights = [weight for _, weight in entries]
    return rng.choices(population, weights=weights, k=1)[0]


class Generator:
    """Builds the whole dataset from one seeded PRNG.

    Args:
        seed: The PRNG seed. Changing it changes every generated value.
    """

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self._used_force_numbers: set[str] = set()
        self._used_usernames: set[str] = set()

    # -- People ------------------------------------------------------------

    def _make_name(self, female_share: float = 0.30) -> tuple[str, str, bool]:
        """Return ``(given, surname, is_female)``.

        Roughly 30% women, per §7.2 — a national force, not a uniform sample.
        """
        is_female = self.rng.random() < female_share
        pool = ref.FEMALE_GIVEN_NAMES if is_female else ref.MALE_GIVEN_NAMES
        return self.rng.choice(pool), self.rng.choice(ref.SURNAMES), is_female

    def _unique_username(self, given: str, surname: str) -> str:
        """Return a unique ``firstname.surname`` username."""
        base = f"{given}.{surname}".lower()
        candidate = base
        suffix = 2
        while candidate in self._used_usernames:
            candidate = f"{base}{suffix}"
            suffix += 1
        self._used_usernames.add(candidate)
        return candidate

    def _unique_force_number(self) -> str:
        """Return a unique five-digit force number."""
        while True:
            candidate = str(self.rng.randint(40000, 49999))
            if candidate not in self._used_force_numbers:
                self._used_force_numbers.add(candidate)
                return candidate

    def _phone(self) -> str:
        """Return a phone number in '+256 772 419 273' form, using real prefixes."""
        prefix = self.rng.choice(ref.PHONE_PREFIXES)[1:]
        return f"+256 {prefix} {self.rng.randint(0, 999):03d} {self.rng.randint(0, 999):03d}"

    def _rank_for_years(self, years: int) -> str:
        """Pick a rank whose service band contains ``years`` (§7.2).

        A four-year officer is never an SSP. Where no band fits, the closest band is
        used rather than inventing an implausible pairing.
        """
        candidates = [
            code
            for code, (low, high) in ref.RANK_YEARS_BAND.items()
            if low <= years <= high and code in ref.FRONTEND_KNOWN_RANKS
        ]
        if candidates:
            weights = dict(ref.TRAINER_RANK_WEIGHTS)
            return self.rng.choices(
                candidates, weights=[weights.get(c, 1) for c in candidates], k=1
            )[0]
        return "AIP" if years < 6 else "ACP"

    def _years_for_rank(self, rank_code: str) -> int:
        """Pick a plausible number of years of service for a rank (§7.2)."""
        low, high = ref.RANK_YEARS_BAND.get(rank_code, (3, 26))
        return self.rng.randint(low, high)

    def _profile_completeness(self) -> int:
        """Pick a profile-completeness score from three realistic bands.

        Most profiles are decent but imperfect, a minority are thin, and a third are
        essentially complete. A uniform distribution would make every trainer's
        confidence band identical and hide the low-data caveat the SRS wants visible.
        """
        band = _weighted_choice(self.rng, (("thin", 20), ("fair", 45), ("full", 35)))
        bounds = {"thin": (45, 65), "fair": (66, 85), "full": (86, 100)}[band]
        return self.rng.randint(*bounds)

    # -- Users -------------------------------------------------------------

    def build_users(self) -> list[GenUser]:
        """Build the four demo accounts followed by the wider staff roster.

        The demo accounts come first and at fixed indices so that ``scripts/seed.py``
        and ``scripts/reset.py`` can refer to them positionally without a lookup.
        """
        hq = "Police Headquarters Naguru"
        hrd = "Human Resource Development"
        users: list[GenUser] = [
            GenUser(
                index=0,
                username="admin.training",
                full_name="Grace Nabirye",
                email="grace.nabirye@upf.go.ug",
                role_name=RoleName.TRAINING_ADMINISTRATOR,
                rank_code="SSP",
                station_name=hq,
                directorate_name=hrd,
                account_status="ACTIVE",
                last_login_at=_at(NOW - datetime.timedelta(days=1), 8, 12),
                created_at=_at(NOW - datetime.timedelta(days=400)),
                is_demo=True,
            ),
            GenUser(
                index=1,
                username="officer.training",
                full_name="Joseph Okello",
                email="joseph.okello@upf.go.ug",
                role_name=RoleName.TRAINING_OFFICER,
                rank_code="ASP",
                station_name=hq,
                directorate_name=hrd,
                account_status="ACTIVE",
                last_login_at=_at(NOW - datetime.timedelta(days=1), 7, 45),
                created_at=_at(NOW - datetime.timedelta(days=400)),
                is_demo=True,
            ),
            GenUser(
                index=2,
                username="trainer",
                full_name="Sarah Mugisha",
                email="sarah.mugisha@upf.go.ug",
                role_name=RoleName.TRAINER,
                rank_code="IP",
                station_name="Kibuli",
                directorate_name="Criminal Investigations",
                account_status="ACTIVE",
                last_login_at=_at(NOW - datetime.timedelta(days=2), 16, 30),
                created_at=_at(NOW - datetime.timedelta(days=380)),
                is_demo=True,
            ),
            GenUser(
                index=3,
                username="sysadmin",
                full_name="Denis Byaruhanga",
                email="denis.byaruhanga@upf.go.ug",
                role_name=RoleName.SYSTEM_ADMINISTRATOR,
                rank_code="SP",
                station_name=hq,
                directorate_name="Information & Communication Technology",
                account_status="ACTIVE",
                last_login_at=_at(NOW, 6, 5),
                created_at=_at(NOW - datetime.timedelta(days=410)),
                is_demo=True,
            ),
        ]
        # Reserve both the demo usernames *and* the name tokens their emails are
        # built from. The demo accounts sign in as `trainer` but their address is
        # sarah.mugisha@upf.go.ug — and "Sarah Mugisha" is drawn from the same name
        # pools as the 812 generated trainers, so without this a pool trainer
        # eventually claims that address and trips the UNIQUE constraint on email.
        for reserved in (
            "admin.training",
            "officer.training",
            "trainer",
            "sysadmin",
            "grace.nabirye",
            "joseph.okello",
            "sarah.mugisha",
            "denis.byaruhanga",
        ):
            self._used_usernames.add(reserved)

        # Staff accounts that are not trainers: officers, administrators, and ICT.
        staff_roles: tuple[tuple[str, str, str], ...] = (
            (RoleName.TRAINING_OFFICER, "ASP", hrd),
            (RoleName.TRAINING_ADMINISTRATOR, "SSP", hrd),
            (RoleName.SYSTEM_ADMINISTRATOR, "ASP", "Information & Communication Technology"),
            (RoleName.TRAINING_OFFICER, "SP", hrd),
        )
        for offset in range(STAFF_USER_COUNT):
            given, surname, _ = self._make_name()
            role_name, rank_code, directorate = staff_roles[offset % len(staff_roles)]
            status = _weighted_choice(
                self.rng, (("ACTIVE", 88), ("SUSPENDED", 6), ("DEACTIVATED", 6))
            )
            created = NOW - datetime.timedelta(days=self.rng.randint(60, 500))
            if status == "DEACTIVATED":
                last_login = _at(NOW - datetime.timedelta(days=self.rng.randint(30, 120)))
            else:
                last_login = _at(
                    NOW - datetime.timedelta(days=self.rng.randint(0, 20)),
                    self.rng.randint(6, 18),
                    self.rng.randint(0, 59),
                )
            username = self._unique_username(given, surname)
            users.append(
                GenUser(
                    index=len(users),
                    username=username,
                    full_name=f"{given} {surname}",
                    # Derived from the *disambiguated* username, not the raw name.
                    # 812 trainers drawn from 40 given names and 38 surnames collide
                    # constantly, and `email` is UNIQUE CITEXT — deriving it from the
                    # one value already guaranteed unique is the only stable fix.
                    email=f"{username}@upf.go.ug",
                    role_name=role_name,
                    rank_code=rank_code,
                    station_name=hq,
                    directorate_name=directorate,
                    account_status=status,
                    last_login_at=last_login,
                    created_at=_at(created),
                )
            )
        return users

    # -- Trainers ----------------------------------------------------------

    def build_trainers(self, users: list[GenUser]) -> list[GenTrainer]:
        """Build 812 trainers: four curated heroes, then the wider pool.

        The heroes exist so the featured prediction run tells a story on first login
        (§7.4). Their attributes are chosen, not random, so that ranks 1 and 2 land
        within 1.4 points of each other and the Weight Studio visibly changes the
        outcome. :func:`assert_fixtures` verifies this held.
        """
        trainers: list[GenTrainer] = []
        station_names = [s.name for s in ref.STATIONS if s.station_type != "TRAINING_INSTITUTION"]

        def enlistment_for(years: int) -> datetime.date:
            """Back-date enlistment so it agrees with years of service."""
            return NOW - datetime.timedelta(days=years * 365 + self.rng.randint(0, 200))

        # --- Hero 0: the `trainer` demo account. Deepest specialisation. ---
        trainers.append(
            GenTrainer(
                index=0,
                user_index=2,
                force_number=self._unique_force_number(),
                rank_code="IP",
                station_name="Kibuli",
                directorate_name="Criminal Investigations",
                date_of_enlistment=enlistment_for(13),
                years_experience=13,
                availability_status=AvailabilityStatus.AVAILABLE,
                contact_number=self._phone(),
                bio=(
                    "Cybercrime investigator with the Directorate of Criminal Investigations. "
                    "Instructs on digital evidence handling and online fraud."
                ),
                profile_completeness=95,
                full_name="Sarah Mugisha",
                qualifications=[
                    (
                        "MSc, Criminal Justice",
                        "MASTERS",
                        "Police Senior Command and Staff College Bwebajja",
                    )
                ],
                qualification_years=[2018],
                specializations=[("Cybercrime Investigation", "EXPERT", 9)],
            )
        )

        # --- Hero 1: breadth. Second specialisation in the same group earns the
        # +10 breadth bonus, which is what makes the top-two race close. ---
        hero_specs: tuple[
            tuple[
                int,
                int,
                str,
                str,
                str,
                list[tuple[str, str, int | None]],
                list[tuple[str, str, str]],
                int,
                int,
            ],
            ...,
        ] = (
            (
                1,
                12,
                "ASP",
                "Jinja Road",
                "Criminal Investigations",
                [
                    ("Cybercrime Investigation", "ADVANCED", 8),
                    ("Criminal Investigation", "ADVANCED", 10),
                ],
                [
                    (
                        "MSc, Criminal Justice",
                        "MASTERS",
                        "Police Senior Command and Staff College Bwebajja",
                    )
                ],
                92,
                2017,
            ),
            (
                2,
                10,
                "IP",
                "Kira Road",
                "Criminal Investigations",
                [("Cybercrime Investigation", "EXPERT", 7)],
                [("BA, Social Sciences", "BACHELORS", "Police Training School Kabalye")],
                85,
                2019,
            ),
            # Hero 3 is the cold-start case: twenty years of service and genuine
            # expertise, but never once formally evaluated as an instructor. He must
            # score into the top five on credentials alone while carrying LOW
            # confidence, so the honest low-data caveat is visible on first login
            # (§7.4.2). His strength is what makes the point — a weak candidate with
            # no evaluations would just look like a weak candidate.
            (
                3,
                20,
                "ASP",
                "Police Headquarters Naguru",
                "Information & Communication Technology",
                [("Cybercrime Investigation", "EXPERT", 14)],
                [
                    (
                        "MSc, Criminal Justice",
                        "MASTERS",
                        "Police Senior Command and Staff College Bwebajja",
                    )
                ],
                70,
                2016,
            ),
        )
        hero_names = ("Betty Nabirye", "Godfrey Businge", "Ibrahim Wekesa")
        for position, spec in enumerate(hero_specs):
            (
                idx,
                years,
                rank,
                station,
                directorate,
                hero_areas,
                hero_quals,
                profile,
                qual_year,
            ) = spec
            trainers.append(
                GenTrainer(
                    index=idx,
                    user_index=-1,  # assigned below
                    force_number=self._unique_force_number(),
                    rank_code=rank,
                    station_name=station,
                    directorate_name=directorate,
                    date_of_enlistment=enlistment_for(years),
                    years_experience=years,
                    availability_status=AvailabilityStatus.AVAILABLE,
                    contact_number=self._phone(),
                    bio=None,
                    profile_completeness=profile,
                    full_name=hero_names[position],
                    qualifications=hero_quals,
                    qualification_years=[qual_year],
                    specializations=hero_areas,
                )
            )

        # --- The remaining pool. --------------------------------------------
        # Cybercrime is common because the featured course is a *basic* one, and it
        # is skewed to lower proficiency and capped below EXPERT so the curated
        # heroes lead on merit rather than by suppressing the field.
        cyber_proficiency: tuple[tuple[str, int], ...] = (
            ("BASIC", 58),
            ("INTERMEDIATE", 36),
            ("ADVANCED", 6),
        )
        general_proficiency: tuple[tuple[str, int], ...] = (
            ("BASIC", 55),
            ("INTERMEDIATE", 34),
            ("ADVANCED", 9),
            ("EXPERT", 2),
        )
        qualification_pool: tuple[tuple[str, int], ...] = (
            ("CERTIFICATE", 14),
            ("DIPLOMA", 30),
            ("BACHELORS", 34),
            ("POSTGRAD_DIPLOMA", 10),
            ("MASTERS", 11),
            ("DOCTORATE", 1),
        )
        availability_pool: tuple[tuple[str, int], ...] = (
            (AvailabilityStatus.AVAILABLE, 68),
            (AvailabilityStatus.ASSIGNED, 26),
            (AvailabilityStatus.UNAVAILABLE, 6),
        )
        other_areas = [
            a.name for a in ref.SPECIALIZATION_AREAS if a.name != "Cybercrime Investigation"
        ]

        for index in range(4, TRAINER_COUNT):
            given, surname, _ = self._make_name()
            rank_code = _weighted_choice(self.rng, ref.TRAINER_RANK_WEIGHTS)
            years = self._years_for_rank(rank_code)

            specs: list[tuple[str, str, int | None]] = []
            has_cyber = self.rng.random() < 0.93
            if has_cyber:
                specs.append(
                    (
                        "Cybercrime Investigation",
                        _weighted_choice(self.rng, cyber_proficiency),
                        self.rng.randint(1, max(1, years - 1)),
                    )
                )
            extra_count = self.rng.randint(0 if has_cyber else 1, 2)
            for area in self.rng.sample(other_areas, extra_count):
                specs.append(
                    (
                        area,
                        _weighted_choice(self.rng, general_proficiency),
                        self.rng.randint(1, max(1, years - 1)),
                    )
                )

            quals: list[tuple[str, str, str]] = []
            years_obtained: list[int] = []
            for _ in range(self.rng.randint(1, 2)):
                level = _weighted_choice(self.rng, qualification_pool)
                from_police = self.rng.random() < 0.40
                pool = (
                    [i.name for i in ref.INSTITUTIONS if i.institution_type == "POLICE"]
                    if from_police
                    else [i.name for i in ref.INSTITUTIONS if i.institution_type != "POLICE"]
                )
                quals.append((ref.QUALIFICATION_NAMES[level], level, self.rng.choice(pool)))
                years_obtained.append(self.rng.randint(2005, 2022))

            trainers.append(
                GenTrainer(
                    index=index,
                    user_index=-1,
                    force_number=self._unique_force_number(),
                    rank_code=rank_code,
                    station_name=self.rng.choice(station_names),
                    directorate_name=_AREA_DIRECTORATE.get(specs[0][0], "Operations"),
                    date_of_enlistment=enlistment_for(years),
                    years_experience=years,
                    availability_status=_weighted_choice(self.rng, availability_pool),
                    contact_number=self._phone(),
                    bio=None,
                    profile_completeness=self._profile_completeness(),
                    full_name=f"{given} {surname}",
                    qualifications=quals,
                    qualification_years=years_obtained,
                    specializations=specs,
                )
            )

        # Every trainer needs a user account. Hero 0 reuses the `trainer` demo
        # account; the rest get one each. The frontend mocks reference 812 trainer
        # users that do not exist in their own `users` array — the relational model
        # will not tolerate that (conflict C9).
        for trainer in trainers:
            if trainer.index == 0:
                continue
            given, _, surname = trainer.full_name.partition(" ")
            username = self._unique_username(given, surname)
            users.append(
                GenUser(
                    index=len(users),
                    username=username,
                    full_name=trainer.full_name,
                    email=f"{username}@upf.go.ug",
                    role_name=RoleName.TRAINER,
                    rank_code=trainer.rank_code,
                    station_name=trainer.station_name,
                    directorate_name=trainer.directorate_name,
                    account_status="ACTIVE",
                    last_login_at=_at(
                        NOW - datetime.timedelta(days=self.rng.randint(0, 45)),
                        self.rng.randint(6, 19),
                        self.rng.randint(0, 59),
                    ),
                    created_at=_at(NOW - datetime.timedelta(days=self.rng.randint(120, 500))),
                )
            )
            trainer.user_index = users[-1].index

        return trainers

    # -- Programmes --------------------------------------------------------

    def build_programmes(self) -> list[GenProgramme]:
        """Build 46 programmes spread across roughly 18 months and every status.

        Programme 0 is the featured one. The status plan is fixed rather than random:
        the dashboard's counts ("3 predictions ready", "2 evaluations outstanding")
        are part of the narrative, and a random plan would make them drift.
        """
        templates: tuple[tuple[str, str, str], ...] = (
            (
                "Basic Cybercrime Investigation Course — Intake {n}",
                "Cybercrime Investigation",
                "Initial Training",
            ),
            (
                "Advanced Cybercrime Investigation Course",
                "Cybercrime Investigation",
                "Specialised Skills",
            ),
            ("Criminal Investigation Refresher", "Criminal Investigation", "Refresher"),
            ("Community Policing Refresher, {region} Region", "Community Policing", "Refresher"),
            (
                "Public Order Management Pre-Deployment Training",
                "Public Order Management",
                "Pre-Deployment",
            ),
            ("Scene of Crime Management Course", "Scene of Crime Management", "Specialised Skills"),
            ("Digital Forensics Level 2", "Digital Forensics", "Specialised Skills"),
            (
                "Traffic Law Enforcement and Road Safety Course",
                "Traffic Management and Road Safety",
                "Specialised Skills",
            ),
            ("Anti-Corruption and Professional Standards Seminar", "Anti-Corruption", "Refresher"),
            (
                "Child and Family Protection Unit Training",
                "Child and Family Protection",
                "Specialised Skills",
            ),
            ("Marine Search and Rescue Course", "Marine Operations", "Specialised Skills"),
            ("Canine Handler Induction Course", "Canine Handling", "Induction"),
            (
                "Intelligence Analysis Foundation Course",
                "Intelligence Analysis",
                "Initial Training",
            ),
            (
                "Firearms Instructor Refresher",
                "Firearms and Tactical Training",
                "Instructor Development",
            ),
            (
                "Records and Registry Management Workshop",
                "Records and Registry Management",
                "Specialised Skills",
            ),
            ("Counter-Terrorism First Responder Course", "Counter-Terrorism", "Pre-Deployment"),
            ("Fire and Rescue Operations Refresher", "Fire and Rescue Operations", "Refresher"),
            (
                "Instructor Development Course — Intake {n}",
                "Cybercrime Investigation",
                "Instructor Development",
            ),
        )
        venue_for: dict[str, str] = {
            "Cybercrime Investigation": "Police Training School, Kabalye",
            "Criminal Investigation": "Kibuli",
            "Community Policing": "Mbale",
            "Public Order Management": "Field Force Unit Training School, Kabalye",
            "Scene of Crime Management": "Kibuli",
            "Digital Forensics": "Police Headquarters Naguru",
            "Traffic Management and Road Safety": "Police Senior Command and Staff College, Bwebajja",
            "Anti-Corruption": "Police Senior Command and Staff College, Bwebajja",
            "Child and Family Protection": "Police Headquarters Naguru",
            "Marine Operations": "Marine Training School, Kajjansi",
            "Canine Handling": "Canine Training School, Nsambya",
            "Intelligence Analysis": "Anti-Terrorism Training School, Olilim",
            "Firearms and Tactical Training": "Police Training School, Kabalye",
            "Records and Registry Management": "Police Headquarters Naguru",
            "Counter-Terrorism": "Anti-Terrorism Training School, Olilim",
            "Fire and Rescue Operations": "Fire and Rescue Training School, Nsambya",
        }
        regions = ("Elgon", "Aswa West", "Rwizi", "West Nile", "Busoga East", "Kigezi")

        programmes: list[GenProgramme] = [
            GenProgramme(
                index=0,
                title="Basic Cybercrime Investigation Course — Intake 14",
                category_name="Initial Training",
                required_area_name="Cybercrime Investigation",
                minimum_experience=3,
                minimum_qualification_code=None,
                start_date=NOW + datetime.timedelta(days=24),
                end_date=NOW + datetime.timedelta(days=35),
                station_name="Police Training School, Kabalye",
                expected_participants=40,
                status=ProgrammeStatus.PREDICTED,
                created_at=_at(NOW - datetime.timedelta(days=12)),
                requirements_set_at=_at(NOW - datetime.timedelta(days=10)),
                created_by_user_index=1,
            )
        ]

        # Fixed status plan for the remaining 45. The first ten EVALUATED slots are
        # forced into the Investigations discipline group so the heroes accumulate a
        # real, relevant evaluation history rather than a generic one.
        status_plan = (
            [ProgrammeStatus.PREDICTED] * 2
            + [ProgrammeStatus.DRAFT] * 2
            + [ProgrammeStatus.REQUIREMENTS_SET] * 3
            + [ProgrammeStatus.AWAITING_RESPONSE] * 2
            + [ProgrammeStatus.ALLOCATED] * 3
            + [ProgrammeStatus.CONDUCTED] * 2
            + [ProgrammeStatus.CANCELLED]
            + [ProgrammeStatus.EVALUATED] * 30
        )
        investigations_areas = ("Cybercrime Investigation", "Criminal Investigation")
        evaluated_seen = 0
        intake = 15

        for offset, status in enumerate(status_plan):
            index = offset + 1
            title_tpl, area, category = templates[(offset + 1) % len(templates)]

            # Force the first ten EVALUATED programmes into Investigations.
            if status == ProgrammeStatus.EVALUATED:
                if evaluated_seen < 10:
                    area = investigations_areas[evaluated_seen % 2]
                    title_tpl, category = (
                        ("Basic Cybercrime Investigation Course — Intake {n}", "Initial Training")
                        if area == "Cybercrime Investigation"
                        else ("Criminal Investigation Refresher", "Refresher")
                    )
                evaluated_seen += 1

            title = title_tpl.replace("{n}", str(intake)).replace(
                "{region}", self.rng.choice(regions)
            )
            if "{n}" in title_tpl:
                intake += 1

            in_past = status in (
                ProgrammeStatus.EVALUATED,
                ProgrammeStatus.CONDUCTED,
                ProgrammeStatus.ALLOCATED,
            )
            if in_past:
                start = NOW - datetime.timedelta(days=self.rng.randint(30, 500))
            else:
                start = NOW + datetime.timedelta(days=self.rng.randint(10, 90))
            end = start + datetime.timedelta(days=self.rng.randint(4, 12))

            is_draft = status == ProgrammeStatus.DRAFT
            programmes.append(
                GenProgramme(
                    index=index,
                    title=title,
                    category_name=category,
                    # A DRAFT programme genuinely has no requirement yet. That is the
                    # whole point of the nullable FK (§5.4).
                    required_area_name=None if is_draft else area,
                    minimum_experience=0 if is_draft else self.rng.choice((2, 3, 5, 8)),
                    minimum_qualification_code=(
                        None
                        if is_draft or self.rng.random() >= 0.30
                        else self.rng.choice(("DIPLOMA", "BACHELORS"))
                    ),
                    start_date=start,
                    end_date=end,
                    station_name=venue_for.get(area, "Police Headquarters Naguru"),
                    expected_participants=self.rng.choice((20, 25, 30, 35, 40, 50)),
                    status=status,
                    created_at=_at(start - datetime.timedelta(days=self.rng.randint(14, 40))),
                    requirements_set_at=(
                        None
                        if is_draft
                        else _at(start - datetime.timedelta(days=self.rng.randint(8, 20)))
                    ),
                    created_by_user_index=1,
                )
            )
        return programmes

    # -- The chronological simulation --------------------------------------

    def simulate(
        self, trainers: list[GenTrainer], programmes: list[GenProgramme]
    ) -> tuple[list[GenRun], list[GenAllocation], list[GenEvaluation], list[GenUnavailability]]:
        """Replay the system's history in date order, producing runs and decisions.

        This is the heart of the seed. Rather than fabricating a consistent-looking
        snapshot, it **replays** what would have happened: programmes are processed
        oldest first, each prediction run sees only the evaluations that existed on
        its own date, and each allocation updates the workload that later runs score
        against. The result is a dataset whose causality survives inspection — an
        officer can open any run and the numbers reconcile with the history preceding
        it.

        Returns:
            The runs, allocations, evaluations, and unavailability windows.
        """
        scoring_view = {t.index: self._to_seed_trainer(t) for t in trainers}
        runs: list[GenRun] = []
        allocations: list[GenAllocation] = []
        evaluations: list[GenEvaluation] = []
        unavailability: list[GenUnavailability] = []

        # Curated hero evaluation scores. These produce the exact means that put
        # ranks 1 and 2 of the featured run within 1.4 points of each other (§7.4.1).
        # Hero 3 is absent by design: a top-five candidate with no evaluations at all,
        # so the LOW-confidence caveat is visible on first login (§7.4.2).
        hero_scores: dict[int, list[Decimal]] = {
            0: [
                Decimal("4.5"),
                Decimal("4.5"),
                Decimal("5.0"),
                Decimal("4.5"),
                Decimal("4.5"),
                Decimal("4.5"),
            ],
            1: [Decimal("5.0"), Decimal("5.0"), Decimal("5.0"), Decimal("4.5"), Decimal("5.0")],
            2: [Decimal("4.5"), Decimal("4.5"), Decimal("4.0")],
        }
        hero_remaining = {k: list(v) for k, v in hero_scores.items()}

        # The over-reliance fixture (§7.4.6): one trainer allocated four times in six
        # months while equally-qualified peers have none. This is the pattern the SRS
        # problem statement describes, and the utilisation chart is empty without it.
        over_allocated = -1  # resolved below, once the recent programmes are known

        runnable = [
            p
            for p in programmes
            if p.status
            in (
                ProgrammeStatus.PREDICTED,
                ProgrammeStatus.AWAITING_RESPONSE,
                ProgrammeStatus.ALLOCATED,
                ProgrammeStatus.CONDUCTED,
                ProgrammeStatus.EVALUATED,
            )
            and p.required_area_name is not None
        ]

        def run_date(programme: GenProgramme) -> datetime.date:
            """When the prediction was generated: shortly before the course starts."""
            if programme.start_date <= NOW:
                return programme.start_date - datetime.timedelta(days=self.rng.randint(8, 20))
            return NOW - datetime.timedelta(days=self.rng.randint(1, 9))

        dated = sorted(((run_date(p), p) for p in runnable), key=lambda pair: pair[0])

        # Pre-select the over-reliance fixture up front (§7.4.6). Two ordering traps
        # made the opportunistic version fail: a trainer only appears in runs whose
        # specialisation they hold, and an allocation approved shortly *before* a
        # course that started 180 days ago falls outside a 180-day window. So the
        # candidate is chosen to maximise coverage of genuinely recent courses, and
        # the window is tightened to 150 days to leave room for the approval lag.
        recent = [
            programme
            for _when, programme in dated
            if programme.status
            in (ProgrammeStatus.EVALUATED, ProgrammeStatus.CONDUCTED, ProgrammeStatus.ALLOCATED)
            and programme.start_date <= NOW
            and (NOW - programme.start_date).days <= 150
        ]
        over_allocated, over_allocated_targets = self._pick_over_allocated(trainers, recent)

        for generated_on, programme in dated:
            seed_programme = self._to_seed_programme(programme)
            pool = [scoring_view[t.index] for t in trainers]
            result = run_prediction(
                trainers=pool,
                programme=seed_programme,
                weights=DEFAULT_WEIGHTS,
                now=generated_on,
            )
            top_total = result.ranked[0].total if result.ranked else Decimal(0)

            predictions: list[GenPrediction] = []
            for position, candidate in enumerate(result.ranked, start=1):
                counterfactual = (
                    build_counterfactual(candidate, top_total, DEFAULT_WEIGHTS)
                    if 2 <= position <= 5
                    else None
                )
                predictions.append(
                    GenPrediction(
                        trainer_index=candidate.trainer.trainer_id,
                        prediction_score=candidate.total,
                        confidence_level=candidate.confidence_level,
                        confidence_band=candidate.confidence_band,
                        rank_position=position,
                        breakdown=candidate.breakdown,
                        rationale=build_rationale(candidate, seed_programme),
                        counterfactual=counterfactual,
                    )
                )

            run = GenRun(
                programme_index=programme.index,
                generated_at=_at(generated_on, self.rng.randint(8, 17), self.rng.randint(0, 59)),
                candidate_pool_size=result.candidate_pool_size,
                excluded_count=len(result.excluded),
                ranked_count=len(result.ranked),
                elapsed_ms=1400 if programme.index == 0 else self.rng.randint(900, 2400),
                generated_by_user_index=0,
                predictions=predictions,
                exclusions=[
                    GenExclusion(
                        trainer_index=e.trainer_id,
                        reason=e.reason,
                        reason_detail=e.reason_detail,
                        business_rule=e.business_rule,
                    )
                    for e in result.excluded
                ],
            )
            run_index = len(runs)
            runs.append(run)

            if programme.status == ProgrammeStatus.PREDICTED or not predictions:
                continue

            # --- Choose who gets allocated. --------------------------------
            chosen: list[GenPrediction] = []
            is_investigations = (
                _DISCIPLINE_GROUP.get(programme.required_area_name or "") == "Investigations"
            )

            if programme.status == ProgrammeStatus.EVALUATED and is_investigations:
                # Heroes first, deliberately, so their evaluation history is the
                # curated one that makes the featured race close.
                for hero_index in (0, 1, 2):
                    if not hero_remaining[hero_index]:
                        continue
                    match = next((p for p in predictions if p.trainer_index == hero_index), None)
                    if match is not None:
                        chosen.append(match)

            if not chosen:
                # Organic: take the top one or two, skipping the curated heroes so
                # their histories stay exactly as scripted.
                wanted = 2 if self.rng.random() < 0.4 else 1
                for selected in predictions:
                    if selected.trainer_index in (0, 1, 2, 3):
                        continue
                    chosen.append(selected)
                    if len(chosen) == wanted:
                        break

            # Force the over-reliance fixture onto its pre-selected programmes.
            if programme.index in over_allocated_targets:
                match = next((p for p in predictions if p.trainer_index == over_allocated), None)
                if match is not None and match not in chosen:
                    chosen.append(match)

            for selected in chosen:
                allocation_index = len(allocations)
                approval = _at(
                    generated_on + datetime.timedelta(days=self.rng.randint(1, 4)),
                    self.rng.randint(9, 16),
                    self.rng.randint(0, 59),
                )
                status_map: dict[str, str] = {
                    ProgrammeStatus.AWAITING_RESPONSE: AllocationStatus.PENDING_TRAINER,
                    ProgrammeStatus.ALLOCATED: AllocationStatus.CONFIRMED,
                    ProgrammeStatus.CONDUCTED: AllocationStatus.CONDUCTED,
                    ProgrammeStatus.EVALUATED: AllocationStatus.EVALUATED,
                }
                allocation_status = status_map[programme.status]
                responded = (
                    None
                    if allocation_status == AllocationStatus.PENDING_TRAINER
                    else approval + datetime.timedelta(days=self.rng.randint(1, 3))
                )
                allocations.append(
                    GenAllocation(
                        index=allocation_index,
                        programme_index=programme.index,
                        trainer_index=selected.trainer_index,
                        run_index=run_index,
                        rank_position=selected.rank_position,
                        status=allocation_status,
                        approval_date=approval,
                        remarks=self.rng.choice(
                            ("Approved as recommended.", "Best fit for the intake.", None)
                        ),
                        frozen_score=selected.prediction_score,
                        frozen_rank_position=selected.rank_position,
                        frozen_breakdown=selected.breakdown,
                        frozen_weights={k: float(v) for k, v in DEFAULT_WEIGHTS.items()},
                        frozen_rationale=selected.rationale,
                        weights_were_simulated=False,
                        decline_reason=None,
                        declined_at=None,
                        responded_at=responded,
                        approved_by_user_index=0,
                    )
                )

                view = scoring_view[selected.trainer_index]
                if allocation_status in (
                    AllocationStatus.PENDING_TRAINER,
                    AllocationStatus.CONFIRMED,
                    AllocationStatus.CONDUCTED,
                ):
                    view.current_allocations += 1

                if programme.status != ProgrammeStatus.EVALUATED:
                    continue

                # Record the evaluation, which becomes visible to every later run.
                if hero_remaining.get(selected.trainer_index):
                    score = hero_remaining[selected.trainer_index].pop(0)
                else:
                    score = Decimal(
                        self.rng.choice(("3.0", "3.5", "4.0", "4.0", "4.5", "4.5", "5.0"))
                    )
                evaluated_on = programme.end_date + datetime.timedelta(days=self.rng.randint(2, 14))
                evaluations.append(
                    GenEvaluation(
                        allocation_index=allocation_index,
                        trainer_index=selected.trainer_index,
                        programme_index=programme.index,
                        score_awarded=score,
                        evaluator_comments=self.rng.choice(ref.EVALUATOR_COMMENTS),
                        evaluation_date=evaluated_on,
                        evaluated_by_user_index=0,
                    )
                )
                view.evaluations.append(
                    SeedEvaluation(
                        programme_id=programme.index,
                        discipline_group=_DISCIPLINE_GROUP.get(programme.required_area_name or ""),
                        score_awarded=score,
                        evaluation_date=evaluated_on,
                    )
                )

        # --- Fixture 3: a decline, corroborated by an absence window. -------
        self._apply_decline_fixture(programmes, allocations, unavailability, trainers)

        # --- Ordinary declared absences. ------------------------------------
        unavailability.extend(
            self._build_unavailability(trainers, exclude={u.trainer_index for u in unavailability})
        )

        return runs, allocations, evaluations, unavailability

    def _pick_over_allocated(
        self, trainers: list[GenTrainer], recent: list[GenProgramme]
    ) -> tuple[int, set[int]]:
        """Choose the over-relied-upon trainer and the courses they will be given.

        §7.4.6. Picks whoever can clear the gates on the most *recent* courses:
        available, experienced enough for any minimum, degree-qualified, and holding
        the required specialisation. That breadth is precisely why a real training
        office over-uses such a person — they are the safe choice everywhere — which
        is the habit the SRS problem statement asks TPS to make visible.

        Args:
            trainers: The full pool.
            recent: Recent past programmes, oldest first.

        Returns:
            The trainer's index and the programme indices to allocate them to.

        Raises:
            FixtureError: If no trainer can cover four recent courses.
        """
        degree_levels = {"BACHELORS", "POSTGRAD_DIPLOMA", "MASTERS", "DOCTORATE"}
        best: tuple[int, list[int]] = (-1, [])

        for trainer in trainers[4:]:
            if trainer.availability_status != AvailabilityStatus.AVAILABLE:
                continue
            if not any(level in degree_levels for _n, level, _i in trainer.qualifications):
                continue
            areas = {area for area, _level, _yrs in trainer.specializations}
            covered = [
                programme.index
                for programme in recent
                if programme.required_area_name in areas
                and trainer.years_experience >= programme.minimum_experience
            ]
            if len(covered) > len(best[1]):
                best = (trainer.index, covered)
            if len(covered) >= 4:
                break

        if len(best[1]) < 4:
            raise FixtureError(
                "Fixture 6: no trainer can be allocated to four recent courses. "
                f"Best candidate covers {len(best[1])}."
            )
        return best[0], set(best[1][:4])

    def _apply_decline_fixture(
        self,
        programmes: list[GenProgramme],
        allocations: list[GenAllocation],
        unavailability: list[GenUnavailability],
        trainers: list[GenTrainer],
    ) -> None:
        """Turn one pending allocation into a decline backed by a real absence window.

        §7.4.3. The mocks carry the decline as a bare string. Here the reason is
        corroborated by a ``trainer_unavailability`` row covering the same dates, so
        the decline is a fact the system can verify rather than an assertion it merely
        repeats.
        """
        pending = [a for a in allocations if a.status == AllocationStatus.PENDING_TRAINER]
        if not pending:
            return
        allocation = pending[0]
        programme = programmes[allocation.programme_index]
        allocation.status = AllocationStatus.DECLINED
        allocation.decline_reason = "Committed to court testimony in Jinja for the same period."
        allocation.declined_at = allocation.approval_date + datetime.timedelta(days=2)
        allocation.responded_at = allocation.declined_at
        unavailability.append(
            GenUnavailability(
                trainer_index=allocation.trainer_index,
                start_date=programme.start_date - datetime.timedelta(days=1),
                end_date=programme.end_date + datetime.timedelta(days=1),
                reason="Court testimony, Jinja Chief Magistrate's Court.",
                category=UnavailabilityCategory.COURT,
            )
        )
        _ = trainers  # kept for signature symmetry with the other fixture builders

    def _build_unavailability(
        self, trainers: list[GenTrainer], exclude: set[int]
    ) -> list[GenUnavailability]:
        """Generate ordinary absence windows for the unavailable trainers.

        One window per trainer only. The ``EXCLUDE USING gist`` constraint forbids
        overlapping windows for a single trainer, and generating one apiece means the
        seed cannot trip it — which is the point of choosing a constraint the data
        naturally satisfies rather than one that must be worked around.
        """
        windows: list[GenUnavailability] = []
        reasons: tuple[tuple[str, str], ...] = (
            (UnavailabilityCategory.LEAVE, "Annual leave."),
            (UnavailabilityCategory.STUDY, "Full-time study leave."),
            (UnavailabilityCategory.DEPLOYMENT, "Operational deployment."),
            (UnavailabilityCategory.MEDICAL, "Medical leave on recommendation."),
            (UnavailabilityCategory.COURT, "Court attendance."),
        )
        for trainer in trainers:
            if trainer.index in exclude:
                continue
            if trainer.availability_status != AvailabilityStatus.UNAVAILABLE:
                continue
            category, reason = self.rng.choice(reasons)
            start = NOW + datetime.timedelta(days=self.rng.randint(-20, 40))
            windows.append(
                GenUnavailability(
                    trainer_index=trainer.index,
                    start_date=start,
                    end_date=start + datetime.timedelta(days=self.rng.randint(5, 45)),
                    reason=reason,
                    category=category,
                )
            )
        return windows

    # -- Conversions to the scoring engine's view ---------------------------

    def _to_seed_trainer(self, trainer: GenTrainer) -> SeedTrainer:
        """Flatten a generated trainer into the shape the scoring engine consumes."""
        return SeedTrainer(
            trainer_id=trainer.index,
            full_name=trainer.full_name,
            rank_code=trainer.rank_code,
            force_number=trainer.force_number,
            years_experience=trainer.years_experience,
            availability_status=trainer.availability_status,
            current_allocations=0,
            profile_completeness=trainer.profile_completeness,
            qualifications=[
                SeedQualification(
                    level_code=level,
                    level_order=_QUALIFICATION_ORDER[level],
                    level_score=_QUALIFICATION_SCORE[level],
                    institution_name=institution,
                    institution_is_police=institution in _POLICE_INSTITUTIONS,
                )
                for _name, level, institution in trainer.qualifications
            ],
            specializations=[
                SeedSpecialization(
                    area_name=area,
                    discipline_group=_DISCIPLINE_GROUP.get(area),
                    proficiency_code=level,
                    proficiency_score=_PROFICIENCY_SCORE[level],
                )
                for area, level, _years in trainer.specializations
            ],
            evaluations=[],
        )

    def _to_seed_programme(self, programme: GenProgramme) -> SeedProgramme:
        """Flatten a generated programme into the shape the scoring engine consumes."""
        area = programme.required_area_name or ""
        code = programme.minimum_qualification_code
        return SeedProgramme(
            programme_id=programme.index,
            title=programme.title,
            required_area_name=area,
            discipline_group=_DISCIPLINE_GROUP.get(area),
            minimum_experience=programme.minimum_experience,
            minimum_qualification_order=_QUALIFICATION_ORDER[code] if code else None,
            minimum_qualification_code=code,
            start_date=programme.start_date,
            end_date=programme.end_date,
        )

    # -- Audit and notifications -------------------------------------------

    def build_audit(
        self,
        users: list[GenUser],
        programmes: list[GenProgramme],
        runs: list[GenRun],
        allocations: list[GenAllocation],
        evaluations: list[GenEvaluation],
    ) -> list[GenAudit]:
        """Build the audit trail: every seeded decision, then routine activity.

        Decision entries come first and are derived from the records themselves, so
        the trail genuinely corresponds to the data rather than being decorative.
        Routine sign-in and export activity backfills to roughly 600 entries.
        """
        entries: list[GenAudit] = []
        role_of = {u.index: u.role_name for u in users}

        def add(
            actor: int | None,
            action: str,
            entity_type: str | None,
            entity_ref: int | None,
            detail: str,
            when: datetime.datetime,
        ) -> None:
            entries.append(
                GenAudit(
                    actor_user_index=actor,
                    actor_role=role_of.get(actor) if actor is not None else None,
                    action=action,
                    entity_type=entity_type,
                    entity_ref=entity_ref,
                    detail=detail,
                    ip_address=f"10.20.{self.rng.randint(0, 40)}.{self.rng.randint(2, 254)}",
                    created_at=when,
                )
            )

        for programme in programmes:
            add(
                programme.created_by_user_index,
                AuditAction.PROGRAMME_CREATED,
                "TRAINING_PROGRAMME",
                programme.index,
                f'Created "{programme.title}"',
                programme.created_at,
            )
            if programme.requirements_set_at is not None:
                add(
                    programme.created_by_user_index,
                    AuditAction.REQUIREMENTS_DEFINED,
                    "TRAINING_PROGRAMME",
                    programme.index,
                    f'Requirements defined for "{programme.title}"',
                    programme.requirements_set_at,
                )

        for run in runs:
            add(
                run.generated_by_user_index,
                AuditAction.PREDICTION_GENERATED,
                "PREDICTION_RUN",
                run.programme_index,
                f"Ranked {run.ranked_count}, excluded {run.excluded_count}, "
                f"in {run.elapsed_ms / 1000:.1f}s",
                run.generated_at,
            )

        for allocation in allocations:
            add(
                allocation.approved_by_user_index,
                AuditAction.ALLOCATION_APPROVED,
                "ALLOCATION",
                allocation.index,
                f"Approved allocation #{allocation.index + 1}",
                allocation.approval_date,
            )
            if allocation.status == AllocationStatus.DECLINED and allocation.declined_at:
                add(
                    None,
                    AuditAction.ASSIGNMENT_DECLINED,
                    "ALLOCATION",
                    allocation.index,
                    allocation.decline_reason or "",
                    allocation.declined_at,
                )

        for evaluation in evaluations:
            add(
                evaluation.evaluated_by_user_index,
                AuditAction.EVALUATION_RECORDED,
                "PERFORMANCE_EVALUATION",
                evaluation.trainer_index,
                f"Recorded {evaluation.score_awarded}/5",
                _at(evaluation.evaluation_date, self.rng.randint(9, 17)),
            )

        # --- Fixture 8: sign-in failures and one lockout, so System Health is
        # not an empty chart on first login (§7.4.8). ---
        locked_user = 5 if len(users) > 5 else 0
        lockout_day = NOW - datetime.timedelta(days=3)
        for attempt in range(3):
            add(
                locked_user,
                AuditAction.LOGIN_FAILED,
                "USER",
                locked_user,
                "Failed sign-in attempt: incorrect password",
                _at(lockout_day, 8, 14 + attempt),
            )
        add(
            locked_user,
            AuditAction.ACCOUNT_LOCKED,
            "USER",
            locked_user,
            "Account locked for 15 minutes after 3 consecutive failed attempts (FR-01)",
            _at(lockout_day, 8, 17),
        )

        routine: tuple[tuple[str, str], ...] = (
            (AuditAction.LOGIN_SUCCESS, "Signed in"),
            (AuditAction.LOGIN_FAILED, "Failed sign-in attempt"),
            (AuditAction.LOGOUT, "Signed out"),
            (AuditAction.REPORT_EXPORTED, "Exported a report to PDF"),
            (AuditAction.WEIGHTS_SIMULATED, "Simulated weighting in the Weight Studio"),
            (AuditAction.UNAUTHORISED_ATTEMPT, "Blocked access to a restricted route"),
        )
        active_users = [u.index for u in users[: STAFF_USER_COUNT + 4]]
        while len(entries) < TARGET_AUDIT_ENTRIES:
            action, detail = self.rng.choice(routine)
            when = _at(
                NOW - datetime.timedelta(days=self.rng.randint(0, 45)),
                self.rng.randint(6, 20),
                self.rng.randint(0, 59),
            )
            add(self.rng.choice(active_users), action, None, None, detail, when)

        entries.sort(key=lambda e: e.created_at)
        return entries

    def build_notifications(self, users: list[GenUser]) -> list[GenNotification]:
        """Build 18 notifications for the demo accounts."""
        notifications: list[GenNotification] = []

        def notify(
            recipient: int,
            message: str,
            kind: str,
            age_hours: int,
            link: str | None,
            read: bool = False,
        ) -> None:
            sent = _at(NOW, 12) - datetime.timedelta(hours=age_hours)
            notifications.append(
                GenNotification(
                    recipient_user_index=recipient,
                    message=message,
                    type=kind,
                    link_to=link,
                    status=NotificationStatus.READ if read else NotificationStatus.UNREAD,
                    delivery_status=DeliveryStatus.SENT,
                    sent_date=sent,
                    read_at=sent + datetime.timedelta(hours=2) if read else None,
                )
            )

        notify(
            2,
            "You have a pending assignment: Digital Forensics Level 2.",
            NotificationType.ASSIGNMENT,
            5,
            "/my-assignments",
        )
        notify(
            2,
            "Your evaluation for Scene of Crime Management Course was recorded (4.5/5).",
            NotificationType.EVALUATION,
            40,
            "/my-performance",
            True,
        )
        notify(
            0,
            "A trainer declined an allocation and needs your review.",
            NotificationType.APPROVAL,
            8,
            "/allocations",
        )
        notify(
            0,
            "3 predictions are ready for your review.",
            NotificationType.REMINDER,
            12,
            "/dashboard",
        )
        notify(
            1,
            "Requirements are outstanding for 2 of your requests.",
            NotificationType.REMINDER,
            20,
            "/programmes",
            True,
        )

        filler = (
            "A new training request was submitted.",
            "An allocation was confirmed.",
            "A performance evaluation was recorded.",
            "System backup completed successfully.",
        )
        while len(notifications) < NOTIFICATION_COUNT:
            notify(
                self.rng.choice((0, 1, 2)),
                self.rng.choice(filler),
                self.rng.choice(
                    (
                        NotificationType.SYSTEM,
                        NotificationType.APPROVAL,
                        NotificationType.EVALUATION,
                        NotificationType.REMINDER,
                    )
                ),
                self.rng.randint(24, 400),
                None,
                self.rng.random() < 0.6,
            )
        _ = users
        return notifications

    # -- Orchestration -----------------------------------------------------

    def build(self) -> Dataset:
        """Generate the complete dataset.

        Order matters and must not be rearranged: every call consumes the shared
        PRNG, so moving one line changes every value generated after it.
        """
        users = self.build_users()
        trainers = self.build_trainers(users)
        programmes = self.build_programmes()
        runs, allocations, evaluations, unavailability = self.simulate(trainers, programmes)
        audit = self.build_audit(users, programmes, runs, allocations, evaluations)
        notifications = self.build_notifications(users)
        return Dataset(
            users=users,
            trainers=trainers,
            unavailability=unavailability,
            programmes=programmes,
            runs=runs,
            allocations=allocations,
            evaluations=evaluations,
            audit=audit,
            notifications=notifications,
        )


def generate(seed: int) -> Dataset:
    """Generate the dataset for a given PRNG seed.

    Args:
        seed: The deterministic seed (§7.1).

    Returns:
        The complete generated dataset.
    """
    return Generator(seed).build()


class FixtureError(AssertionError):
    """Raised when a §7.4 narrative fixture did not materialise."""


def assert_fixtures(dataset: Dataset) -> list[str]:
    """Verify all eight §7.4 narrative fixtures, raising if any is missing.

    The seed's job is not merely to produce rows — it is to produce a dataset that
    *tells a story on first login*. A fixture that silently fails to materialise
    would show up as an empty chart during a demonstration, which is exactly the
    moment it cannot be fixed. Checking here converts that into a loud failure at
    seed time.

    Args:
        dataset: The generated dataset.

    Returns:
        One human-readable confirmation line per fixture.

    Raises:
        FixtureError: If any fixture is absent.
    """
    lines: list[str] = []
    featured = next(r for r in dataset.runs if r.programme_index == FEATURED_PROGRAMME_INDEX)

    # 1 — ranks 1 and 2 within 1.4 points.
    if len(featured.predictions) < 2:
        raise FixtureError("Featured run produced fewer than two ranked candidates.")
    gap = featured.predictions[0].prediction_score - featured.predictions[1].prediction_score
    if gap > Decimal("1.4"):
        raise FixtureError(
            f"Fixture 1: featured top-two gap is {gap}, must be <= 1.4 so the "
            "Weight Studio visibly changes the outcome."
        )
    lines.append(
        f"1. Featured top-two gap {gap} pts "
        f"({featured.predictions[0].prediction_score} vs {featured.predictions[1].prediction_score})"
    )

    # 2 — a LOW-confidence, zero-evaluation candidate in the top five.
    low = [p for p in featured.predictions[:5] if p.confidence_band == "LOW"]
    if not low:
        raise FixtureError("Fixture 2: no LOW-confidence candidate in the featured top five.")
    lines.append(
        f"2. {len(low)} LOW-confidence candidate(s) in the top five "
        f"(ranks {', '.join(str(p.rank_position) for p in low)})"
    )

    # 3 — a decline corroborated by an unavailability window.
    declined = [a for a in dataset.allocations if a.status == AllocationStatus.DECLINED]
    if not declined:
        raise FixtureError("Fixture 3: no declined allocation.")
    corroborated = any(
        u.trainer_index == declined[0].trainer_index and u.category == UnavailabilityCategory.COURT
        for u in dataset.unavailability
    )
    if not corroborated:
        raise FixtureError("Fixture 3: the declined allocation has no matching absence window.")
    lines.append("3. Declined allocation corroborated by a COURT unavailability window")

    # 4 — a CONDUCTED programme with no evaluation yet.
    evaluated_programmes = {e.programme_index for e in dataset.evaluations}
    conducted = [
        p
        for p in dataset.programmes
        if p.status == ProgrammeStatus.CONDUCTED and p.index not in evaluated_programmes
    ]
    if not conducted:
        raise FixtureError("Fixture 4: no CONDUCTED-but-unevaluated programme.")
    lines.append(f"4. {len(conducted)} CONDUCTED programme(s) awaiting evaluation")

    # 5 — a populated Exclusion Ledger.
    reasons: dict[str, int] = {}
    for exclusion in featured.exclusions:
        reasons[exclusion.reason] = reasons.get(exclusion.reason, 0) + 1
    if reasons.get("UNAVAILABLE", 0) < 8:
        raise FixtureError("Fixture 5: fewer than 8 UNAVAILABLE exclusions on the featured run.")
    if reasons.get("MISSING_SPECIALIZATION", 0) < 5:
        raise FixtureError("Fixture 5: fewer than 5 missing-specialisation exclusions.")
    lines.append(
        "5. Featured Exclusion Ledger: "
        + ", ".join(f"{count} {reason}" for reason, count in sorted(reasons.items()))
    )

    # 6 — the over-reliance pattern.
    counts: dict[int, int] = {}
    six_months_ago = NOW - datetime.timedelta(days=185)
    for allocation in dataset.allocations:
        if allocation.approval_date.date() >= six_months_ago:
            counts[allocation.trainer_index] = counts.get(allocation.trainer_index, 0) + 1
    busiest = max(counts.items(), key=lambda pair: pair[1], default=(0, 0))
    if busiest[1] < 4:
        raise FixtureError(
            f"Fixture 6: busiest trainer has {busiest[1]} allocations in six months, need >= 4."
        )
    lines.append(f"6. Trainer #{busiest[0]} allocated {busiest[1]}x in six months (over-reliance)")

    # 7 — evaluations spanning at least four quarters.
    quarters = {
        (e.evaluation_date.year, (e.evaluation_date.month - 1) // 3) for e in dataset.evaluations
    }
    if len(quarters) < 4:
        raise FixtureError(f"Fixture 7: evaluations span only {len(quarters)} quarters, need >= 4.")
    lines.append(f"7. Evaluations span {len(quarters)} quarters")

    # 8 — sign-in failures and a lockout.
    failed = sum(1 for a in dataset.audit if a.action == AuditAction.LOGIN_FAILED)
    locked = sum(1 for a in dataset.audit if a.action == AuditAction.ACCOUNT_LOCKED)
    if failed < 3 or locked < 1:
        raise FixtureError(
            f"Fixture 8: {failed} LOGIN_FAILED and {locked} ACCOUNT_LOCKED entries; "
            "need >= 3 and >= 1."
        )
    lines.append(f"8. Audit trail carries {failed} LOGIN_FAILED and {locked} ACCOUNT_LOCKED")

    return lines


__all__ = [
    "NOW",
    "Dataset",
    "GenAllocation",
    "GenAudit",
    "GenEvaluation",
    "GenExclusion",
    "GenNotification",
    "GenPrediction",
    "GenProgramme",
    "GenRun",
    "GenTrainer",
    "GenUnavailability",
    "GenUser",
    "Generator",
    "SeedEvaluation",
    "SeedProgramme",
    "SeedQualification",
    "SeedSpecialization",
    "SeedTrainer",
    "build_counterfactual",
    "build_rationale",
    "run_prediction",
]
