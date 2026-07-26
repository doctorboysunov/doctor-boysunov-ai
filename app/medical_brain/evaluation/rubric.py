"""Rubric for Universal Medical Brain prompt architecture."""

from __future__ import annotations

from dataclasses import dataclass

from app.medical_brain.engine import build_medical_brain_input
from app.medical_brain.evaluation.scenarios import MedicalScenario, SCENARIOS
from app.medical_brain.prompts import build_medical_brain_instructions
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.types import ClinicalBrainInput
from app.services.consultation_red_flags import detect_consultation_red_flags
from app.medical_brain.router import route_medical_specialties


@dataclass
class MedicalScenarioResult:
    scenario_id: str
    title: str
    passed: bool
    score: float
    routing_primary: str
    routing_secondary: list[str]
    checks: dict[str, bool]
    expert_opens_with: str
    common_ai_mistake: str
    improvement: str

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "passed": self.passed,
            "score": self.score,
            "routing_primary": self.routing_primary,
            "routing_secondary": self.routing_secondary,
            "checks": self.checks,
            "expert_opens_with": self.expert_opens_with,
            "common_ai_mistake": self.common_ai_mistake,
            "improvement": self.improvement,
        }


def _build_instructions(scenario: MedicalScenario) -> tuple[str, object]:
    brain_input = build_medical_brain_input(
        patient_id=1,
        user_message=scenario.opening_message,
        session_messages=[{"role": "user", "content": scenario.opening_message}],
        known_facts={"opening_complaint": scenario.opening_message},
        topics_covered=["opening_complaint"],
        prior_complaints=[],
    )
    memory_input = ClinicalBrainInput(
        patient_id=1,
        user_message=scenario.opening_message,
        complaint_category=brain_input.complaint_category,
        session_messages=brain_input.session_messages,
        known_facts=brain_input.known_facts,
        topics_covered=brain_input.topics_covered,
    )
    memory = retrieve_clinical_memory(memory_input)
    flags = detect_consultation_red_flags(scenario.opening_message)
    instructions = build_medical_brain_instructions(brain_input, memory, flags)
    routing = route_medical_specialties(scenario.opening_message)
    return instructions, routing


def evaluate_medical_scenario(scenario: MedicalScenario) -> MedicalScenarioResult:
    instructions, routing = _build_instructions(scenario)

    primary_ok = routing.primary == scenario.expected_primary or (
        scenario.expected_primary in [routing.primary, *routing.secondary]
    )
    secondary_ok = True
    if scenario.expected_secondary:
        secondary_ok = all(s in [routing.primary, *routing.secondary] for s in scenario.expected_secondary)

    checks = {
        "routing_primary": primary_ok,
        "routing_secondary": secondary_ok,
        "universal_physician_prompt": (
            "experienced physician" in instructions.lower()
            or "senior neurologist" in instructions.lower()
        ),
        "reason_first": "reason first" in instructions.lower() or "reasoning" in instructions.lower(),
        "multi_specialty_coordination": (
            "MULTI-SPECIALTY" in instructions or "multi-specialty" in instructions.lower()
            if scenario.requires_multi_specialty
            else True
        ),
        "specialty_reference": scenario.expected_primary.upper() in instructions.upper()
        or routing.primary.upper() in instructions.upper(),
        "emergency_awareness": (
            "EMERGENCY" in instructions or "emergency" in instructions.lower()
            if scenario.requires_emergency
            else True
        ),
        "one_question_rule": "ONE question" in instructions or "one highest-value" in instructions.lower(),
        "not_a_script": "NOT a script" in instructions or "never follow scripts" in instructions.lower(),
    }

    score = sum(1 for v in checks.values() if v) / len(checks) * 100
    passed = score >= 85 and checks["routing_primary"] and checks["universal_physician_prompt"]

    return MedicalScenarioResult(
        scenario_id=scenario.id,
        title=scenario.title,
        passed=passed,
        score=round(score, 1),
        routing_primary=routing.primary,
        routing_secondary=routing.secondary,
        checks=checks,
        expert_opens_with=scenario.expert_opens_with,
        common_ai_mistake=scenario.common_ai_mistake,
        improvement=scenario.improvement,
    )


def evaluate_all_scenarios() -> list[MedicalScenarioResult]:
    return [evaluate_medical_scenario(s) for s in SCENARIOS]
