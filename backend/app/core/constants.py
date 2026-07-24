"""Domain constants shared by the models, the migrations, and the seed.

Anything here is structural — a name the database itself depends on (a sequence, a
trigger, a function) or a value the schema's ``CHECK`` constraints mirror. Values
that policy may retune live in **rows**, not here (D8, NFR-10): scoring weights are
in ``scoring_policy_weights``, and qualification/proficiency score values are in
their lookup tables.
"""

from __future__ import annotations

from typing import Final

# --- Registry numbers (§5.9) ----------------------------------------------

REGISTRY_PREFIX: Final = "TPS"

#: Document families and the sequence backing each. A sequence — never MAX(id)+1,
#: which produces duplicate registry numbers under concurrent approvals.
REGISTRY_FAMILIES: Final[dict[str, str]] = {
    "REQ": "registry_req_seq",  # training_programmes
    "ALL": "registry_all_seq",  # allocations
    "EVL": "registry_evl_seq",  # performance_evaluations
}

#: Name of the SQL helper installed by migration 0002.
REGISTRY_FUNCTION: Final = "next_registry_number"

# --- Trigger and function names (§5.10) -----------------------------------

FN_SET_UPDATED_AT: Final = "set_updated_at"
FN_PREVENT_AUDIT_MUTATION: Final = "prevent_audit_mutation"
FN_CHECK_POLICY_WEIGHTS: Final = "check_policy_weights_sum"

TRIGGER_UPDATED_AT_SUFFIX: Final = "set_updated_at"

#: The read view built by migration 0003.
VIEW_TRAINER_SCORING_FACTS: Final = "v_trainer_scoring_facts"

# --- Scoring engine constants ---------------------------------------------
# These are algorithm structure, not policy. The *weights* are rows (D8); the
# ceilings and neutral priors below define what a criterion means at all, and
# changing one is a change to the algorithm, reviewed as code.

#: Years of service at which the EXPERIENCE criterion saturates.
EXPERIENCE_CEILING_YEARS: Final = 20

#: Score given when a trainer has no evaluations. A neutral prior, not a zero —
#: a system with no history must not punish the people it has no data about.
PERFORMANCE_COLD_START_SCORE: Final = 55

#: Bonus added when a second specialisation shares the programme's discipline group.
SPECIALIZATION_BREADTH_BONUS: Final = 10

#: Bonus added when any qualification came from a police training institution.
QUALIFICATION_POLICE_INSTITUTION_BONUS: Final = 8

#: Confidence band thresholds (inclusive lower bounds).
CONFIDENCE_HIGH_THRESHOLD: Final = 75
CONFIDENCE_MODERATE_THRESHOLD: Final = 45

#: Evaluations needed before the "relevant evaluations only" path is used.
RELEVANT_EVALUATION_MINIMUM: Final = 2

#: Evaluations at which the confidence depth factor saturates.
CONFIDENCE_EVALUATION_DEPTH_TARGET: Final = 5

# --- Authentication (FR-01) -----------------------------------------------

MAX_LOGIN_ATTEMPTS: Final = 3
LOCKOUT_MINUTES: Final = 15

# --- Seed ------------------------------------------------------------------

#: Password for all four demo accounts (§7.5). Development fixture only.
DEMO_PASSWORD: Final = "Tps@2026#Demo"

#: Bootstrap administrator username. ``scripts/reset.py`` preserves this account
#: and the other three demo accounts when wiping transactional data.
BOOTSTRAP_USERNAME: Final = "admin.training"

DEMO_USERNAMES: Final[tuple[str, ...]] = (
    "admin.training",
    "officer.training",
    "trainer",
    "sysadmin",
)
