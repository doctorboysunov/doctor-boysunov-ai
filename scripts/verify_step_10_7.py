"""Phase 10.7: Clinical Brain verification."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_10_7.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "clinical-brain-test")
os.environ.setdefault("OPENAI_API_KEY", "clinical-brain-test")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from app.clinical_brain import ClinicalBrainInput, run_clinical_brain  # noqa: E402
from app.clinical_brain.types import ClinicalBrainInternal, ClinicalBrainOutput, DoctorEmrUpdate  # noqa: E402
from app.clinical_brain.knowledge import format_knowledge_reference  # noqa: E402
from app.clinical_brain.memory import retrieve_clinical_memory  # noqa: E402
from app.clinical_brain.parse import parse_clinical_brain_response  # noqa: E402
from app.clinical_brain.prompts import build_clinical_brain_instructions  # noqa: E402
from app.clinical_brain.types import RankedHypothesis  # noqa: E402
from app.services.consultation_ai import run_neurology_turn  # noqa: E402


class TestRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append((name, detail or "failed"))


def main() -> None:
    runner = TestRunner()

    knowledge = format_knowledge_reference("headache")
    runner.check("knowledge_reference_not_script", "majburiy tartib EMAS" in knowledge, knowledge[:120])
    runner.check("knowledge_has_topics", "headache_location" in knowledge or "bosh" in knowledge.lower(), knowledge[:200])

    brain_input = ClinicalBrainInput(
        patient_id=1,
        user_message="Boshim og'riyapti",
        complaint_category="headache",
        session_messages=[{"role": "user", "content": "Boshim og'riyapti"}],
        known_facts={"opening": "Bosh og'rig'i"},
        topics_covered=["opening"],
        prior_complaints=["Oldin migren"],
    )
    memory = retrieve_clinical_memory(brain_input)
    runner.check("memory_retrieved", "Oldin migren" in memory.get("memory_summary", ""), memory.get("memory_summary", "")[:200])

    instructions = build_clinical_brain_instructions(
        brain_input, memory, knowledge, detected_red_flags=[]
    )
    for step in range(1, 8):
        runner.check(f"prompt_step{step}", f"STEP {step}" in instructions, "")
    runner.check("prompt_not_chatbot", "NOT a chatbot" in instructions, "")
    runner.check("prompt_quality_over_speed", "quality beats speed" in instructions or "speed" in instructions.lower(), "")

    payload = {
        "clinical_brain": {
            "step1_patient_meaning": "Bosh og'rig'i shikoyati",
            "step2_memory_summary": "Oldin migren",
            "step3_hypotheses": [
                {"name": "Migren", "probability": "high", "rationale": "Xarakter"},
                {"name": "Tension headache", "probability": "medium", "rationale": "Stress"},
            ],
            "step4_red_flags": [],
            "step4_emergency_assessment": "none",
            "step5_missing_information": ["Boshlanish vaqti"],
            "step6_next_question_topic": "onset",
            "step6_next_question_rationale": "Anamnez uchun muhim",
            "step6_clinical_confidence": "low",
            "step7_stop_asking": False,
            "step7_ready_for_summary": False,
        },
        "patient_reply": "Tushundim. Qachondan beri og'riyapti?",
        "ready_for_help_menu": False,
        "known_facts": {"complaint": "headache"},
        "topics_covered": ["opening"],
        "doctor_emr": {"chief_complaint": "Bosh og'rig'i"},
    }
    parsed = parse_clinical_brain_response(payload, detected_red_flags=[])
    runner.check("hypotheses_ranked", len(parsed.internal.step3_hypotheses) == 2, "")
    runner.check("hypothesis_order", parsed.internal.step3_hypotheses[0].probability == "high", "")
    runner.check("internal_hidden_from_reply", "Migren" not in parsed.patient_reply, parsed.patient_reply)
    runner.check("emr_has_clinical_brain", "Clinical Brain" in parsed.internal.format_emr_reasoning(), "")

    mock_response = MagicMock()
    mock_response.output_text = json.dumps(payload)

    with patch("app.clinical_brain.engine.client.responses.create", return_value=mock_response):
        with patch("app.clinical_brain.engine.enforce_safety", side_effect=lambda **kw: (kw["ai_response"], {})):
            output = run_clinical_brain(brain_input)

    runner.check("engine_runs_pipeline", output.patient_reply.startswith("Tushundim"), output.patient_reply)
    runner.check("engine_has_hypotheses", len(output.internal.step3_hypotheses) >= 1, "")

    with patch("app.services.consultation_ai.run_medical_brain") as mock_brain:
        from app.medical_brain.types import MedicalBrainInternal, MedicalBrainOutput  # noqa: E402

        mock_brain.return_value = MedicalBrainOutput(
            patient_reply="Salom. Qachondan beri?",
            doctor_emr=DoctorEmrUpdate(chief_complaint="Bosh og'rig'i"),
            internal=MedicalBrainInternal(step1_patient_meaning="test", primary_specialty="neurology"),
            primary_specialty="neurology",
        )
        turn = run_neurology_turn(
            category="headache",
            user_message="Boshim og'riyapti",
            session_messages=[{"role": "user", "content": "Boshim og'riyapti"}],
            known_facts={},
            topics_covered=[],
            prior_complaints=[],
            patient_id=1,
        )
    runner.check("neurology_delegates_to_brain", mock_brain.called, "")
    runner.check("neurology_reply", "Qachondan" in turn.patient_reply, turn.patient_reply)

    _report(runner)


def _report(runner: TestRunner) -> None:
    print(f"\n=== Phase 10.7 Clinical Brain: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: Clinical Brain verified")


if __name__ == "__main__":
    main()
