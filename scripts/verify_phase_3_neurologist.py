"""Phase 3 — Senior Neurologist Clinical Intelligence verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_phase_3_neurologist.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "phase3-neuro-test"
os.environ["OPENAI_API_KEY"] = "phase3-neuro-test"

sys.path.insert(0, str(ROOT))

from app.clinical_brain.prompts import build_clinical_brain_instructions  # noqa: E402
from app.clinical_brain.senior_neurologist import (  # noqa: E402
    PHASE_3_VERSION,
    build_closure_summary,
    detect_complaint_clusters,
    format_communication_style_block,
    format_emergency_consultation_ending,
    format_patient_closure_summary,
    format_routine_consultation_ending,
    format_senior_neurologist_principles,
    identify_dominant_complaint,
    ConsultationClosureSummary,
)
from app.clinical_brain.types import ClinicalBrainInput, ClinicalBrainInternal, DoctorEmrUpdate, RankedHypothesis  # noqa: E402
from app.clinical_brain.parse import parse_clinical_brain_response  # noqa: E402
from app.medical_brain.prompts import build_medical_brain_instructions  # noqa: E402
from app.medical_brain.types import MedicalBrainInput  # noqa: E402


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

    runner.check("phase3_version", PHASE_3_VERSION == "3.1.0", PHASE_3_VERSION)

    principles = format_senior_neurologist_principles()
    style = format_communication_style_block()
    runner.check("principles_danger_first", "dangerous" in principles.lower() or "xavf" in principles.lower(), "")
    runner.check("principles_no_prescribe", "NEVER prescribe" in principles, "")
    runner.check("principles_closure", "consultation_closure" in principles, "")
    runner.check("principles_simple_uzbek", "SIMPLE Uzbek" in principles, "")
    runner.check("principles_not_chatgpt", "NOT ChatGPT" in principles, "")
    runner.check("style_warm", "warm" in style.lower(), "")
    runner.check("style_no_duplicate", "duplicate" in style.lower(), "")
    runner.check("style_minimum_questions", "MINIMUM" in style, "")

    multi = "Boshim og'riyapti va belim ham og'riyapti"
    clusters = detect_complaint_clusters(multi)
    runner.check("multi_complaint_detected", len(clusters) >= 2, repr([c.category for c in clusters]))

    dominant = identify_dominant_complaint(multi, "headache")
    runner.check("dominant_has_label", bool(dominant.dominant_label), dominant.dominant_label)
    runner.check("dominant_has_rationale", bool(dominant.rationale), dominant.rationale)
    runner.check("dominant_secondary", len(dominant.secondary_complaints) >= 1, dominant.secondary_complaints)

    stroke_msg = "Qo'lim ishlamay qoldi, nutqim buzildi"
    stroke_dom = identify_dominant_complaint(stroke_msg, "other_neurological")
    runner.check("stroke_dominant", stroke_dom.dominant_category == "stroke", stroke_dom.dominant_category)

    internal = ClinicalBrainInternal(
        step1_patient_meaning="Bosh og'rig'i 3 kundan beri",
        step4_red_flags=["Thunderclap pattern"],
        step4_emergency_assessment="urgent",
        step3_hypotheses=[RankedHypothesis(name="Migren", probability="medium", probability_pct=35.0)],
    )
    closure = build_closure_summary(internal=internal, doctor_emr=DoctorEmrUpdate(), dominant=dominant)
    runner.check("closure_summary", bool(closure.clinical_summary), closure.clinical_summary)
    runner.check("closure_chief", bool(closure.chief_complaint), closure.chief_complaint)
    runner.check("closure_most_likely", bool(closure.most_likely_diagnosis), closure.most_likely_diagnosis)
    runner.check("closure_treatment", bool(closure.treatment_strategy), closure.treatment_strategy)
    runner.check("closure_ranked", bool(closure.ranked_diagnoses), closure.ranked_diagnoses)
    runner.check("closure_red_flags", bool(closure.red_flags), closure.red_flags)
    runner.check("closure_next_step", bool(closure.recommended_next_step), closure.recommended_next_step)
    runner.check("closure_urgent", closure.urgent_referral_required, "")

    routine_closure = ConsultationClosureSummary(
        chief_complaint="Bosh og'rig'i",
        clinical_summary="3 kunlik davomiy bosh og'rig'i",
        most_likely_diagnosis="Migren (35%)",
        urgent_referral_required=False,
    )
    patient_text = format_patient_closure_summary(routine_closure)
    runner.check("patient_routine_ending", "Rahmat" in patient_text and "Doctor Boysunov" in patient_text, patient_text[:160])
    runner.check("patient_booking_options", "videokonsultatsiya" in patient_text and "oflayn" in patient_text, "")

    emergency_closure = ConsultationClosureSummary(
        clinical_summary="O'tkir nevrologik belgilar",
        urgent_referral_required=True,
        urgent_referral_reason="Insult shubhasi",
    )
    emergency_text = format_emergency_consultation_ending(emergency_closure)
    runner.check("emergency_no_online", "onlayn" in emergency_text.lower() and "103" in emergency_text, emergency_text[:120])
    runner.check("patient_no_prescription", "retsept" not in patient_text.lower() or "shart" in patient_text.lower(), "")

    brain_input = ClinicalBrainInput(
        patient_id=1,
        user_message=multi,
        complaint_category="headache",
        session_messages=[{"role": "user", "content": multi}],
        known_facts={},
        topics_covered=[],
    )
    instructions = build_clinical_brain_instructions(
        brain_input,
        memory={"memory_summary": "none", "known_facts": {}, "topics_covered": [], "prior_complaints": [], "conversation_lines": []},
        knowledge_reference="topics",
        detected_red_flags=[],
    )
    runner.check("clinical_prompt_senior", "SENIOR NEUROLOGIST" in instructions, "")
    runner.check("clinical_prompt_communication", "COMMUNICATION STYLE" in instructions, "")
    runner.check("clinical_prompt_ending", "CONSULTATION ENDING" in instructions, "")
    runner.check("clinical_prompt_dominant", "DOMINANT COMPLAINT" in instructions, "")
    runner.check("clinical_prompt_closure_json", "chief_complaint" in instructions and "neurological_syndrome" in instructions, "")
    runner.check("clinical_prompt_must_not_miss", "step3_must_not_miss" in instructions, "")

    med_input = MedicalBrainInput(
        patient_id=1,
        user_message=multi,
        primary_specialty="neurology",
        complaint_category="headache",
        session_messages=[{"role": "user", "content": multi}],
    )
    med_instructions = build_medical_brain_instructions(
        med_input,
        memory={"memory_summary": "none", "known_facts": {}, "topics_covered": [], "prior_complaints": [], "conversation_lines": []},
        detected_red_flags=[],
    )
    runner.check("medical_prompt_senior_neuro", "SENIOR NEUROLOGIST" in med_instructions, "")

    payload = {
        "clinical_brain": {
            "step1_patient_meaning": "Bosh og'rig'i",
            "step3_hypotheses": [{"name": "Migren", "probability": "medium", "probability_pct": 40}],
            "step4_red_flags": [],
            "step4_emergency_assessment": "routine",
            "step7_ready_for_summary": True,
            "step7_stop_asking": True,
            "step6_clinical_confidence": "high",
        },
        "patient_reply": "",
        "ready_for_help_menu": True,
        "consultation_closure": {
            "chief_complaint": "Bosh og'rig'i",
            "clinical_summary": "3 kunlik bosh og'rig'i",
            "associated_symptoms": ["Ko'ngil aynishi"],
            "neurological_syndrome": "Bosh og'rig'i sindromi",
            "most_likely_diagnosis": "Migren (40%)",
            "differential_diagnosis": ["Tension headache (30%)"],
            "red_flags": [],
            "recommended_investigations": ["Neurolog ko'rigi"],
            "treatment_strategy": "Shifokor ko'rigidan keyin individual reja",
            "next_step": "Shifokor ko'rigi",
            "urgent_referral_required": False,
        },
        "doctor_emr": {"chief_complaint": "Bosh og'rig'i", "urgency": "routine"},
    }
    parsed = parse_clinical_brain_response(payload, detected_red_flags=[], user_message=multi)
    runner.check("parse_closure_facts", "consultation_closure" in parsed.known_facts, "")
    runner.check("parse_brief_summary", bool(parsed.brief_summary_for_patient), parsed.brief_summary_for_patient)
    runner.check("parse_patient_closure", "Rahmat" in parsed.patient_reply or "xulosa" in parsed.patient_reply.lower(), parsed.patient_reply[:120])

    with patch("app.medical_brain.engine.client.responses.create") as mock_create:
        mock_resp = MagicMock()
        mock_resp.output_text = __import__("json").dumps(payload)
        mock_create.return_value = mock_resp
        from app.medical_brain.engine import run_medical_brain

        out = run_medical_brain(med_input)
        runner.check("engine_closure_persisted", "consultation_closure" in out.known_facts, "")
        runner.check("engine_dominant_complaint", out.known_facts.get("dominant_complaint"), "")

    print()
    print("=" * 72)
    print(f"PHASE 3 NEUROLOGIST VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 3 Senior Neurologist Clinical Intelligence OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
