"""Universal Medical Brain — production clinical AI platform core."""

from app.medical_brain.engine import (
    build_medical_brain_input,
    medical_brain_to_legacy_summary,
    run_medical_brain,
)
from app.medical_brain.router import is_medical_consultation_trigger, route_medical_specialties
from app.medical_brain.types import MedicalBrainInput, MedicalBrainOutput

__all__ = [
    "MedicalBrainInput",
    "MedicalBrainOutput",
    "build_medical_brain_input",
    "is_medical_consultation_trigger",
    "medical_brain_to_legacy_summary",
    "route_medical_specialties",
    "run_medical_brain",
]
