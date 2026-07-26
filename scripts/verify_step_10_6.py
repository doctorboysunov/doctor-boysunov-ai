"""Phase 10.6: AI-owned conversation state verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_10_6.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "conversation-state-test")
os.environ.setdefault("OPENAI_API_KEY", "conversation-state-test")
os.environ["ADMIN_TELEGRAM_IDS"] = ""

sys.path.insert(0, str(ROOT))

from app.db.connection import init_db  # noqa: E402
from app.repositories.consultation_repository import get_active_session  # noqa: E402
from app.services.consultation_ai import (  # noqa: E402
    COMPLAINT_SWITCH_PROMPT,
    GREETING_RESUME_PROMPT,
    ConversationIntentAnalysis,
    DoctorEmrUpdate,
    NeurologyTurnOutput,
    parse_complaint_clarification,
    parse_session_choice,
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


def _mock_neurology(**kwargs) -> NeurologyTurnOutput:
    return NeurologyTurnOutput(
        patient_reply="Tushundim. Qachondan beri og'riyapti?",
        doctor_emr=DoctorEmrUpdate(chief_complaint="Bosh og'rig'i"),
        topics_covered=["opening_complaint"],
    )


def main() -> None:
    runner = TestRunner()
    init_db()

    runner.eq("parse_session_continue", parse_session_choice("Davom ettiramiz"), "continue")
    runner.eq("parse_session_new", parse_session_choice("Yangi muammo"), "new")
    runner.eq("parse_complaint_new", parse_complaint_clarification("Yangi shikoyat"), "new_complaint")
    runner.eq("parse_complaint_old", parse_complaint_clarification("Oldingi shikoyat"), "continue_previous")

    created = create_patient_intelligently(
        source="telegram", text="Conv State Test 901890001", started_at="2026-07-26"
    )
    runner.check("patient_created", created is not None, "")
    if not created:
        _report(runner)
        return

    patient_id = created.patient_id
    seed_default_location(patient_id)
    create_visit(patient_id, visit_date="2026-07-26")
    user_data: dict = {}

    with patch("app.services.consultation_engine.run_neurology_turn", side_effect=_mock_neurology):
        process_consultation_turn(patient_id, "Boshim og'riyapti", user_data=user_data)

    def intent_greeting(**kwargs) -> ConversationIntentAnalysis:
        return ConversationIntentAnalysis(
            is_greeting=True,
            confidence="high",
            recommended_action="ask_session_choice",
        )

    with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=intent_greeting):
        greeting_turn = process_consultation_turn(patient_id, "Assalomu alaykum", user_data=user_data)

    runner.check("greeting_prompt", GREETING_RESUME_PROMPT in greeting_turn.reply, greeting_turn.reply)
    runner.eq("greeting_phase", greeting_turn.phase, "awaiting_session_choice")

    with patch("app.services.consultation_engine.run_neurology_turn", side_effect=_mock_neurology):
        continue_turn = process_consultation_turn(patient_id, "Davom ettiramiz", user_data=user_data)

    runner.eq("after_continue_phase", continue_turn.phase, "collecting")
    runner.check("continue_resume_text", "davom etamiz" in continue_turn.reply.lower(), continue_turn.reply)

    def intent_topic_change(**kwargs) -> ConversationIntentAnalysis:
        return ConversationIntentAnalysis(
            is_topic_change=True,
            is_new_complaint=True,
            detected_complaint_category="low_back_pain",
            confidence="high",
            recommended_action="ask_complaint_clarification",
        )

    with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=intent_topic_change):
        switch_turn = process_consultation_turn(patient_id, "Belim og'riyapti", user_data=user_data)

    runner.check("complaint_switch_prompt", COMPLAINT_SWITCH_PROMPT in switch_turn.reply, switch_turn.reply)
    runner.eq("complaint_switch_phase", switch_turn.phase, "awaiting_complaint_clarification")

    back_mock = NeurologyTurnOutput(
        patient_reply="Bel og'rig'i qachondan beri?",
        doctor_emr=DoctorEmrUpdate(chief_complaint="Bel og'rig'i"),
        topics_covered=["opening_complaint"],
    )

    with patch("app.services.consultation_engine.run_neurology_turn", return_value=back_mock):
        new_complaint_turn = process_consultation_turn(
            patient_id, "Yangi shikoyat", user_data=user_data
        )

    runner.check("new_complaint_started", "bel" in new_complaint_turn.reply.lower(), new_complaint_turn.reply)
    session = get_active_session(patient_id)
    runner.check("new_session_active", session is not None, repr(session))
    if session:
        runner.eq("new_session_category", session.complaint_category, "low_back_pain")

    patient2 = create_patient_intelligently(
        source="telegram", text="Conv State Test 901890002", started_at="2026-07-26"
    )
    if patient2:
        pid2 = patient2.patient_id
        seed_default_location(pid2)
        create_visit(pid2, visit_date="2026-07-26")
        ud2: dict = {}

        with patch("app.services.consultation_engine.run_neurology_turn", side_effect=_mock_neurology):
            process_consultation_turn(pid2, "Boshim og'riyapti", user_data=ud2)

        def intent_continue(**kwargs) -> ConversationIntentAnalysis:
            return ConversationIntentAnalysis(
                is_answering_previous_question=True,
                confidence="high",
                recommended_action="continue_session",
            )

        answer_mock = NeurologyTurnOutput(
            patient_reply="3 kundan beri ekan — qayeri og'riyapti?",
            topics_covered=["onset"],
        )
        with patch("app.services.consultation_engine.run_conversation_intent_analysis", side_effect=intent_continue):
            with patch("app.services.consultation_engine.run_neurology_turn", return_value=answer_mock):
                answer_turn = process_consultation_turn(pid2, "3 kun oldin", user_data=ud2)

        runner.check("confident_continue", "qayeri" in answer_turn.reply.lower(), answer_turn.reply)
        runner.eq("confident_continue_phase", answer_turn.phase, "collecting")

    _report(runner)


def _report(runner: TestRunner) -> None:
    print(f"\n=== Phase 10.6 Conversation State: {runner.passed}/{runner.total} passed ===")
    for name, detail in runner.failed:
        print(f"FAIL: {name} — {detail}")
    if runner.failed:
        sys.exit(1)
    print("PASS: AI-owned conversation state verified")


if __name__ == "__main__":
    main()
