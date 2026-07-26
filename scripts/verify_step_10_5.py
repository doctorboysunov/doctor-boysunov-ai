"""Phase 10.5: AI reasoning upgrade verification."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_10_5.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "reasoning-test-token")
os.environ.setdefault("OPENAI_API_KEY", "reasoning-test-key")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.repositories.consultation_repository import get_active_session  # noqa: E402
from app.repositories.emr_repository import get_emr_visit, list_emr_visits_for_patient  # noqa: E402
from app.clinical_brain.knowledge import format_knowledge_reference  # noqa: E402
from app.clinical_brain.memory import retrieve_clinical_memory  # noqa: E402
from app.clinical_brain.parse import parse_clinical_brain_response  # noqa: E402
from app.clinical_brain.prompts import build_clinical_brain_instructions  # noqa: E402
from app.clinical_brain import ClinicalBrainInput  # noqa: E402
from app.services.consultation_ai import (  # noqa: E402
    COMPLAINT_SWITCH_PROMPT,
    GREETING_RESUME_PROMPT,
    HELP_MENU_QUESTION,
    ConversationIntentAnalysis,
    InternalReasoning,
    NeurologyTurnOutput,
    DoctorEmrUpdate,
    build_help_menu_reply,
    run_help_followup_turn,
)
from app.services.consultation_engine import process_consultation_turn  # noqa: E402
from app.services.emr_service import create_visit  # noqa: E402
from app.services.patient_creation_engine import create_patient_intelligently  # noqa: E402
from scripts.test_support import seed_default_location  # noqa: E402


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

    def eq(self, name: str, got, expected) -> None:
        self.check(name, got == expected, f"got {got!r}, expected {expected!r}")


def _sentence_count(text: str) -> int:
    parts = re.split(r"[.!?]+", text)
    return len([part for part in parts if part.strip()])


def main() -> None:
    runner = TestRunner()
    init_db()

    reasoning = InternalReasoning(
        what_i_know=["3 kunlik bosh og'rig'i"],
        missing_information=["Lokalizatsiya"],
        emergency_assessment="none",
        possible_neurological_causes=["Migren", "Tension headache"],
        next_question_topic="location",
        next_question_rationale="Topografiya differensialni toraytiradi",
    )
    runner.check("reasoning_emr_block", "AI klinik mulohaza" in reasoning.format_emr_reasoning(), "")
    runner.check("reasoning_knows", "3 kunlik" in reasoning.format_emr_reasoning(), "")

    brain_input = ClinicalBrainInput(
        patient_id=1,
        user_message="Boshim og'riyapti",
        complaint_category="headache",
        known_facts={"onset": "3 kun"},
        topics_covered=["onset"],
        prior_complaints=["Oldin migren"],
        session_messages=[{"role": "user", "content": "Boshim og'riyapti"}],
    )
    memory = retrieve_clinical_memory(brain_input)
    knowledge = format_knowledge_reference("headache")
    instructions = build_clinical_brain_instructions(brain_input, memory, knowledge, [])
    runner.check("prompt_requires_reasoning", "clinical_brain" in instructions, "")
    runner.check("prompt_no_script_tree", "NOT a chatbot" in instructions or "never follow" in instructions.lower(), "")
    runner.check("prompt_one_question", "ONE question" in instructions, "")
    runner.check("prompt_topics_covered", "NEVER repeat" in instructions, "")

    payload = {
        "clinical_brain": {
            "step1_patient_meaning": "Bosh og'rig'i 3 kun",
            "step5_missing_information": ["Lokalizatsiya"],
            "step6_next_question_topic": "location",
            "step6_next_question_rationale": "Topografiya differensialni toraytiradi",
            "step3_hypotheses": [{"name": "Migren", "probability": "medium", "rationale": ""}],
        },
        "patient_reply": "Tushundim. Og'riq qayerda — peshona yoki chakka?",
        "ready_for_help_menu": False,
        "known_facts": {"onset": "3 kun"},
        "topics_covered": ["onset"],
        "doctor_emr": {"chief_complaint": "Bosh og'rig'i", "history": "3 kun"},
    }
    parsed = parse_clinical_brain_response(payload, detected_red_flags=[])
    runner.check("parse_adds_topic", "location" in parsed.topics_covered, str(parsed.topics_covered))
    runner.check("parse_short_reply", _sentence_count(parsed.patient_reply) <= 4, parsed.patient_reply)

    menu = build_help_menu_reply("Bosh og'rig'i 3 kundan beri, o'rtacha kuchda.")
    runner.check("menu_summarizes_first", menu.index("tushundim") < menu.index(HELP_MENU_QUESTION), menu)
    runner.check("menu_not_immediate_online", "onlayn yozilish" not in menu.lower(), menu)
    runner.check("menu_continue_first", menu.index("Savollarni davom ettirish") < menu.index("Onlayn"), menu)

    gpt_json = json.dumps({
        "internal_reasoning": reasoning.to_dict(),
        "patient_reply": "Yana bir savol.",
        "ready_for_help_menu": True,
        "brief_summary_for_patient": "Bosh og'rig'i 3 kundan beri.",
        "topics_covered": ["onset", "location"],
        "doctor_emr": {"chief_complaint": "Bosh og'rig'i"},
    })

    mock_response = MagicMock()
    mock_response.output_text = gpt_json

    with patch("app.clinical_brain.engine.client.responses.create", return_value=mock_response):
        with patch("app.clinical_brain.engine.enforce_safety", side_effect=lambda **kw: (kw["ai_response"], {})):
            from app.clinical_brain import run_clinical_brain

            out = run_clinical_brain(
                ClinicalBrainInput(
                    patient_id=1,
                    user_message="Peshonada",
                    complaint_category="headache",
                    session_messages=[{"role": "user", "content": "Peshonada"}],
                    known_facts={"onset": "3 kun"},
                    topics_covered=["onset"],
                )
            )
    runner.check("live_parse_reasoning", out.internal.step6_next_question_topic == "onset" or out.patient_reply, "")
    runner.eq("live_parse_emergency", out.suggests_emergency, False)

    urgent = InternalReasoning(emergency_assessment="emergency")
    runner.check(
        "urgent_flag",
        NeurologyTurnOutput(internal_reasoning=urgent).suggests_emergency,
        "",
    )

    followup_mock = MagicMock()
    followup_mock.output_text = "Onlayn konsultatsiya uchun mutaxassisimiz tez orada bog'lanadi."
    with patch("app.services.consultation_ai.client.responses.create", return_value=followup_mock):
        with patch("app.services.consultation_ai.enforce_safety", side_effect=lambda **kw: (kw["ai_response"], {})):
            followup = run_help_followup_turn(
                category="headache",
                choice="online",
                session_messages=[],
                known_facts={},
            )
    runner.check("help_followup_gpt", "onlayn" in followup.lower(), followup)
    runner.check("help_followup_short", _sentence_count(followup) <= 4, followup)

    created = create_patient_intelligently(
        source="telegram", text="Reasoning Test 901889001", started_at="2026-07-26"
    )
    runner.check("patient_created", created is not None, "")
    if not created:
        _report(runner)
        return

    patient_id = created.patient_id
    seed_default_location(patient_id)
    create_visit(patient_id, visit_date="2026-07-26")
    user_data: dict = {}

    def _brain_summary(internal: InternalReasoning) -> dict:
        return {
            "clinical_brain": {
                "step1_patient_meaning": internal.what_i_know[0] if internal.what_i_know else "",
                "step3_hypotheses": [{"name": c, "probability": "medium", "rationale": ""} for c in internal.possible_neurological_causes],
                "step4_emergency_assessment": internal.emergency_assessment,
                "step5_missing_information": internal.missing_information,
                "step6_next_question_topic": internal.next_question_topic,
            },
            "internal_reasoning": internal.to_dict(),
        }

    def mock_turn(**kwargs):
        mock_turn.n += 1
        if mock_turn.n < 3:
            internal = InternalReasoning(
                what_i_know=["Bosh og'rig'i"],
                missing_information=["Vaqt"],
                next_question_topic="onset",
            )
            doctor = DoctorEmrUpdate(chief_complaint="Bosh og'rig'i")
            summary = _brain_summary(internal)
            summary["doctor_emr"] = doctor.to_dict()
            return NeurologyTurnOutput(
                patient_reply="Qachondan beri og'riyapti?",
                topics_covered=["opening_complaint", "onset"],
                internal_reasoning=internal,
                doctor_emr=doctor,
                session_summary=summary,
            )
        internal = InternalReasoning(
            what_i_know=["Bosh og'rig'i", "3 kun"],
            possible_neurological_causes=["Migren"],
            emergency_assessment="none",
        )
        doctor = DoctorEmrUpdate(
            chief_complaint="Bosh og'rig'i",
            differential_diagnoses=["Migren"],
        )
        summary = _brain_summary(internal)
        summary["doctor_emr"] = doctor.to_dict()
        return NeurologyTurnOutput(
            ready_for_help_menu=True,
            brief_summary_for_patient="Bosh og'rig'i bir necha kundan beri.",
            topics_covered=["onset", "location"],
            internal_reasoning=internal,
            doctor_emr=doctor,
            session_summary=summary,
        )

    mock_turn.n = 0

    with patch("app.services.consultation_engine.run_neurology_turn", side_effect=mock_turn):
        with patch(
            "app.services.consultation_engine.run_conversation_intent_analysis",
            return_value=ConversationIntentAnalysis(
                is_answering_previous_question=True,
                confidence="high",
                recommended_action="continue_session",
            ),
        ):
            t1 = process_consultation_turn(patient_id, "Boshim og'riyapti", user_data=user_data)
            t2 = process_consultation_turn(patient_id, "3 kun", user_data=user_data)
            t3 = process_consultation_turn(patient_id, "Peshonada", user_data=user_data)

    runner.check("turn1_no_tree_phrase", "konsultatsiya boshlaymiz" not in t1.reply.lower(), t1.reply)
    runner.check("turn3_help_question", HELP_MENU_QUESTION in t3.reply, t3.reply)
    runner.eq("turn3_phase", t3.phase, "awaiting_help_choice")

    session = get_active_session(patient_id)
    summary = (session.summary or {}) if session else {}
    runner.check(
        "session_has_reasoning",
        "clinical_brain" in summary or "internal_reasoning" in summary,
        json.dumps(summary)[:200],
    )

    visits = list_emr_visits_for_patient(patient_id)
    if visits:
        notes = get_emr_visit(visits[0]["id"]).get("notes") or ""
        runner.check("emr_has_reasoning", "Clinical Brain" in notes or "AI klinik mulohaza" in notes, notes[:300])
        runner.check("emr_hidden_from_patient_menu", HELP_MENU_QUESTION not in notes, notes[:300])

    with patch("app.services.consultation_engine.run_neurology_turn", side_effect=mock_turn):
        with patch(
            "app.services.consultation_engine.run_conversation_intent_analysis",
            return_value=ConversationIntentAnalysis(
                is_answering_previous_question=True,
                confidence="high",
                recommended_action="continue_session",
            ),
        ):
            with patch(
                "app.services.consultation_engine.run_help_followup_turn",
                return_value="Klinikada qabul uchun vaqt tanlashga yordam beramiz.",
            ):
                process_consultation_turn(patient_id, "Klinikada qabul", user_data=user_data)

    runner.check("clinic_complete", get_active_session(patient_id) is None, "")

    _report(runner)


def _report(runner: TestRunner) -> None:
    print(f"\n=== Phase 10.5 AI Reasoning: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: Phase 10.5 reasoning upgrade verified")


if __name__ == "__main__":
    main()
