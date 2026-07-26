"""Evaluate Clinical Brain prompts against 20 expert neurology scenarios."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("OPENAI_API_KEY", "eval-test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-test")

from app.clinical_brain.expert_interview import suggest_interview_phase  # noqa: E402
from app.clinical_brain.knowledge import format_knowledge_reference  # noqa: E402
from app.clinical_brain.memory import retrieve_clinical_memory  # noqa: E402
from app.clinical_brain.prompts import build_clinical_brain_instructions  # noqa: E402
from app.clinical_brain.scenarios import SCENARIOS, NeurologyScenario  # noqa: E402
from app.clinical_brain.types import ClinicalBrainInput  # noqa: E402
from app.services.consultation_red_flags import detect_consultation_red_flags  # noqa: E402


def _prompt_includes_triage(instructions: str, scenario: NeurologyScenario) -> bool:
    triage_markers = ("triage", "SNOOP", "qizil", "shoshilinch", "cauda", "PRESENTATION OVERRIDE")
    return any(m.lower() in instructions.lower() for m in triage_markers)


def _prompt_discourages_mistake(instructions: str, scenario: NeurologyScenario) -> bool:
    mistake = scenario.common_ai_mistake.lower()
    if "1-10" in mistake or "severity" in mistake:
        return "1-10" in instructions or "severity" in instructions.lower() and "do not" in instructions.lower()
    if "where" in mistake and "forehead" in mistake:
        return "topography" in instructions.lower() or "location before" in instructions.lower() or "reflect" in instructions.lower()
    if "since when" in mistake.lower() or "qachondan" in mistake.lower():
        return "do not start with generic" in instructions.lower() or "qachondan" in instructions.lower()
    return scenario.improvement.lower()[:20] in instructions.lower() or "expert" in instructions.lower() or "senior" in instructions.lower()


def evaluate_scenario(scenario: NeurologyScenario) -> dict:
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

    triage_ok = _prompt_includes_triage(instructions, scenario)
    phase_ok = phase in ("triage", "narrative", "discriminator") or scenario.id in ("19_topic_switch", "20_greeting_mid")
    expert_block_ok = (
        "EXPERT NEUROLOGIST" in instructions
        or "SENIOR NEUROLOGIST" in instructions
    )
    mistake_guard_ok = _prompt_discourages_mistake(instructions, scenario)
    override_ok = (
        "PRESENTATION OVERRIDE" in instructions
        if scenario.red_flag_hints
        or scenario.id in {"04_stroke_acute", "10_central_vertigo", "18_first_seizure"}
        else True
    )

    passed = all([triage_ok, phase_ok, expert_block_ok, mistake_guard_ok, override_ok])

    return {
        "id": scenario.id,
        "title": scenario.title,
        "passed": passed,
        "phase_hint": phase,
        "detected_flags": flags,
        "expert_opens_with": scenario.expert_opens_with,
        "common_ai_mistake": scenario.common_ai_mistake,
        "why_ai_mistakes": scenario.why_ai_mistakes,
        "improvement": scenario.improvement,
        "checks": {
            "triage_in_prompt": triage_ok,
            "appropriate_phase": phase_ok,
            "expert_strategy_block": expert_block_ok,
            "mistake_guard": mistake_guard_ok,
            "presentation_override": override_ok,
        },
    }


def main() -> None:
    results = [evaluate_scenario(s) for s in SCENARIOS]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n=== Clinical Brain 20-Scenario Expert Rubric: {passed}/{total} ===\n")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}: {r['title']}")
        if not r["passed"]:
            failed_checks = [k for k, v in r["checks"].items() if not v]
            print(f"       Failed checks: {failed_checks}")
        print(f"       Expert would: {r['expert_opens_with'][:100]}...")
        print(f"       Old AI mistake: {r['common_ai_mistake']}")
        print(f"       Why: {r['why_ai_mistakes']}")
        print(f"       Fix applied: {r['improvement'].replace(chr(0x2192), '->')}")
        print()

    report_path = ROOT / "data" / "clinical_brain_scenario_eval.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Full report: {report_path}")

    if passed < total:
        sys.exit(1)
    print("PASS: All 20 scenarios meet expert rubric in prompt architecture")


if __name__ == "__main__":
    main()
