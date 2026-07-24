"""The prediction engine — the core of the system (§5).

Pure, dependency-free, exhaustively tested. No database, no HTTP, no clock.

**This is not machine learning.** It is deterministic weighted multi-criteria decision
analysis. Nothing here is trained, nothing is probabilistic, and the API must never
claim otherwise (§5.1). See ``docs/ALGORITHMS.md``.
"""

from app.services.prediction.confidence import band_for, compute_confidence, compute_recency
from app.services.prediction.criteria import CRITERIA, CRITERION_ORDER, shrunk_mean
from app.services.prediction.engine import (
    WeightsError,
    generate_prediction,
    preview_eligibility,
    score_candidate,
    validate_weights,
)
from app.services.prediction.gates import evaluate_gates, format_date_range
from app.services.prediction.narrative import build_counterfactual, build_rationale
from app.services.prediction.types import (
    CandidateFacts,
    CriterionScore,
    EligibilityPreview,
    Exclusion,
    PredictionRunResult,
    ProgrammeRequirements,
    ScheduleConflict,
    ScoredCandidate,
)

__all__ = [
    "CRITERIA",
    "CRITERION_ORDER",
    "CandidateFacts",
    "CriterionScore",
    "EligibilityPreview",
    "Exclusion",
    "PredictionRunResult",
    "ProgrammeRequirements",
    "ScheduleConflict",
    "ScoredCandidate",
    "WeightsError",
    "band_for",
    "build_counterfactual",
    "build_rationale",
    "compute_confidence",
    "compute_recency",
    "evaluate_gates",
    "format_date_range",
    "generate_prediction",
    "preview_eligibility",
    "score_candidate",
    "shrunk_mean",
    "validate_weights",
]
