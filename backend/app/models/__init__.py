"""Every ORM model, re-exported.

**Alembic autogenerate depends on this module importing every model.** If a model
module is not imported before ``target_metadata`` is read, Alembic does not see the
table — and will cheerfully write a migration that drops it. Adding a model file
without adding it here is therefore a data-loss bug, not a style lapse.
"""

from __future__ import annotations

from app.db.base import Base
from app.models.allocation import Allocation, PerformanceEvaluation
from app.models.identity import RefreshToken, User
from app.models.prediction import Prediction, PredictionExclusion, PredictionRun
from app.models.programme import TrainingProgramme
from app.models.reference import (
    Directorate,
    Institution,
    PoliceRank,
    ProficiencyLevel,
    QualificationLevel,
    Region,
    Role,
    SpecializationArea,
    Station,
    TrainingCategory,
)
from app.models.scoring import ScoringPolicy, ScoringPolicyWeight
from app.models.system import AuditLog, Notification
from app.models.trainer import (
    Trainer,
    TrainerQualification,
    TrainerSpecialization,
    TrainerUnavailability,
)

__all__ = [
    "Allocation",
    "AuditLog",
    "Base",
    "Directorate",
    "Institution",
    "Notification",
    "PerformanceEvaluation",
    "PoliceRank",
    "Prediction",
    "PredictionExclusion",
    "PredictionRun",
    "ProficiencyLevel",
    "QualificationLevel",
    "RefreshToken",
    "Region",
    "Role",
    "ScoringPolicy",
    "ScoringPolicyWeight",
    "SpecializationArea",
    "Station",
    "Trainer",
    "TrainerQualification",
    "TrainerSpecialization",
    "TrainerUnavailability",
    "TrainingCategory",
    "TrainingProgramme",
    "User",
]
