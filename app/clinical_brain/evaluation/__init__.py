"""Production clinical evaluation framework."""

from app.clinical_brain.evaluation.baseline import compare_to_baseline, load_baseline, save_baseline
from app.clinical_brain.evaluation.reporter import build_report, write_improvement_report
from app.clinical_brain.evaluation.rubric import evaluate_scenario
from app.clinical_brain.evaluation.scenario_bank import SCENARIOS_100
from app.clinical_brain.evaluation.types import EvaluationReport, NeurologyScenario, ScenarioEvaluation

__all__ = [
    "SCENARIOS_100",
    "EvaluationReport",
    "NeurologyScenario",
    "ScenarioEvaluation",
    "build_report",
    "compare_to_baseline",
    "evaluate_scenario",
    "load_baseline",
    "save_baseline",
    "write_improvement_report",
]
