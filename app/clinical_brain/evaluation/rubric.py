"""Rubric scoring for Clinical Brain prompt architecture."""

from __future__ import annotations

from app.clinical_brain.evaluation.types import NeurologyScenario, ScenarioEvaluation
from app.clinical_brain.expert_interview import suggest_interview_phase
from app.clinical_brain.types import ClinicalBrainInput
from app.clinical_brain.memory import retrieve_clinical_memory
from app.clinical_brain.knowledge import format_knowledge_reference
from app.clinical_brain.prompts import build_clinical_brain_instructions
from app.services.consultation_red_flags import detect_consultation_red_flags


def build_instructions_for_scenario(scenario: NeurologyScenario) -> tuple[str, list[str], str]:
    brain_input = ClinicalBrainInput(
        patient_id=1,
        user_message=scenario.opening_message,
        complaint_category=scenario.category,  # type: ignore[arg-type]
        session_messages=[{"role": "user", "content": scenario.opening_message}],
        known_facts={"opening_complaint": scenario.opening_message},
        topics_covered=["opening_complaint"],
    )
    memory = retrieve_clinical_memory(brain_input)
    knowledge = format_knowledge_reference(scenario.category)  # type: ignore[arg-type]
    flags = detect_consultation_red_flags(scenario.opening_message)
    instructions = build_clinical_brain_instructions(brain_input, memory, knowledge, flags)
    phase = suggest_interview_phase(
        scenario.category,  # type: ignore[arg-type]
        topics_covered=["opening_complaint"],
        message=scenario.opening_message,
        detected_red_flags=flags,
    )
    return instructions, flags, phase


def _check_triage(instructions: str, scenario: NeurologyScenario) -> bool:
    if not scenario.requires_triage:
        return True
    markers = ("triage", "SNOOP", "qizil", "shoshilinch", "PRESENTATION OVERRIDE", "urgent")
    return any(m.lower() in instructions.lower() for m in markers)


def _check_override(instructions: str, scenario: NeurologyScenario) -> bool:
    if not scenario.requires_override:
        return True
    return "PRESENTATION OVERRIDE" in instructions


def _check_expert_block(instructions: str) -> bool:
    has_persona = (
        "EXPERT NEUROLOGIST" in instructions
        or "SENIOR NEUROLOGIST" in instructions
    )
    return has_persona and "highest-priority incomplete phase" in instructions


def _check_guidelines(instructions: str) -> bool:
    return "CLINICAL GUIDELINES" in instructions and "NOT a script" in instructions


def _check_conversation_quality(instructions: str) -> bool:
    quality_markers = (
        "NOT a chatbot",
        "2-4",
        "Acknowledge",
        "Never sound robotic",
        "Mirror",
    )
    return sum(1 for m in quality_markers if m.lower() in instructions.lower()) >= 3


def _check_clinical_intelligence(instructions: str) -> bool:
    intel_markers = (
        "differential",
        "hypotheses",
        "step6_alternatives_rejected",
        "clinical_confidence",
        "highest-value",
    )
    return sum(1 for m in intel_markers if m.lower() in instructions.lower()) >= 3


def _check_avoid_mistakes(instructions: str, scenario: NeurologyScenario) -> bool:
    lower = instructions.lower()
    if any(p in lower for p in ("do not ask 1-10", "do not start with generic", "never repeat")):
        return True
    for pattern in scenario.avoid_patterns:
        if pattern.lower() in lower and "do not" in lower:
            return True
    return scenario.improvement.lower()[:15] in lower or "expert" in lower or "senior" in lower


def _check_phase(phase: str, scenario: NeurologyScenario) -> bool:
    if scenario.clinical_label in {"greeting", "topic_switch"}:
        return True
    return phase in {"triage", "narrative", "discriminator", "context"}


def evaluate_scenario(scenario: NeurologyScenario) -> ScenarioEvaluation:
    instructions, flags, phase = build_instructions_for_scenario(scenario)
    checks = {
        "triage_when_needed": _check_triage(instructions, scenario),
        "presentation_override": _check_override(instructions, scenario),
        "expert_strategy": _check_expert_block(instructions),
        "clinical_guidelines": _check_guidelines(instructions),
        "clinical_intelligence": _check_clinical_intelligence(instructions),
        "conversation_quality": _check_conversation_quality(instructions),
        "avoid_common_mistakes": _check_avoid_mistakes(instructions, scenario),
        "appropriate_phase": _check_phase(phase, scenario),
    }
    score = sum(1 for v in checks.values() if v) / len(checks) * 100
    passed = score >= 85.0 and all(
        checks[k]
        for k in (
            "expert_strategy",
            "clinical_guidelines",
            "clinical_intelligence",
            "conversation_quality",
        )
    )
    return ScenarioEvaluation(
        scenario_id=scenario.id,
        title=scenario.title,
        clinical_label=scenario.clinical_label,
        passed=passed,
        score=round(score, 1),
        phase_hint=phase,
        detected_flags=flags,
        checks=checks,
        expert_opens_with=scenario.expert_opens_with,
        common_ai_mistake=scenario.common_ai_mistake,
        why_ai_mistakes=scenario.why_ai_mistakes,
        improvement=scenario.improvement,
    )
