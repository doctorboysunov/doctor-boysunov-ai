"""World-class Medical Brain training — 100k+ case generation and optimization."""

from app.medical_brain.training.generator import (
    generate_case,
    generate_cases,
    parameter_space,
    total_case_capacity,
    verify_capacity,
)
from app.medical_brain.training.loop import run_training_evaluation
from app.medical_brain.training.types import PRODUCTION_QUALITY, TARGET_CASE_CAPACITY


def run_continuous_learning_cycle(*args, **kwargs):
    from app.medical_brain.training.continuous_loop import run_continuous_learning_cycle as _run

    return _run(*args, **kwargs)


__all__ = [
    "generate_case",
    "generate_cases",
    "parameter_space",
    "total_case_capacity",
    "verify_capacity",
    "run_training_evaluation",
    "run_continuous_learning_cycle",
    "PRODUCTION_QUALITY",
    "TARGET_CASE_CAPACITY",
]
