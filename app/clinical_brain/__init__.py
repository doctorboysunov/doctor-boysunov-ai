"""Clinical Brain — independent neurology reasoning engine (Phase 10.7 + Phase 3 + Phase 4 Pathways).

Reusable by Telegram bot, mobile apps, web apps, and CRM.
Every patient message passes through the 7-step internal pipeline.
"""

from app.clinical_brain.engine import run_clinical_brain
from app.clinical_brain.senior_neurologist import PHASE_3_VERSION
from app.clinical_brain.types import (
    ClinicalBrainInput,
    ClinicalBrainInternal,
    ClinicalBrainOutput,
    DoctorEmrUpdate,
    RankedHypothesis,
)

__all__ = [
    "ClinicalBrainInput",
    "ClinicalBrainInternal",
    "ClinicalBrainOutput",
    "DoctorEmrUpdate",
    "PHASE_3_VERSION",
    "RankedHypothesis",
    "run_clinical_brain",
]
