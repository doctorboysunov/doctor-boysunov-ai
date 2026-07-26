"""Consultation architecture v6 — continuity, recognition, no auto-restart."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_consultation_architecture.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "arch-v6-test"
os.environ["OPENAI_API_KEY"] = "arch-v6-test"

sys.path.insert(0, str(ROOT))

from app.consultation_intelligence import (  # noqa: E402
    ENGINE_VERSION,
    ConsultationState,
    process_consultation_intelligence_turn,
)
from app.clinical_brain.clinical_pathways.recognition import recognize_pathway, resolve_complaint_category
from app.db.connection import init_db
from app.repositories.consultation_repository import get_active_session
from app.repositories.conversation_repository import upsert_user
from app.services.consultation_classifier import classify_complaint
from app.services.consultation_engine import process_consultation_turn
from scripts.test_support import seed_default_location


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


def _turn(messages: list, answers: dict, text: str):
    messages.append({"role": "user", "content": text})
    result = process_consultation_intelligence_turn(
        user_message=text,
        session_messages=messages,
        answers=answers,
    )
    messages.append({"role": "assistant", "content": result.patient_reply})
    return result


def main() -> None:
    init_db()
    runner = TestRunner()
    runner.check("engine_version_v6", ENGINE_VERSION == "6.0.0", ENGINE_VERSION)

    # Complaint recognition — left leg pain must not fall back to other_neurological
    leg = "Chap oyoq og'riyapti"
    runner.check(
        "classifier_not_other",
        classify_complaint(leg) != "other_neurological",
        classify_complaint(leg),
    )
    runner.check(
        "resolve_not_other",
        resolve_complaint_category(leg) != "other_neurological",
        resolve_complaint_category(leg),
    )
    pid, _, _ = recognize_pathway(leg)
    runner.check("pathway_lumbar", pid == "lumbar_radiculopathy", pid)

    english = "I have left leg pain radiating from my back"
    eid, _, _ = recognize_pathway(english)
    runner.check("english_leg_pain", eid == "lumbar_radiculopathy", eid)

    # Multi-turn continuity — same session, advancing questions
    answers: dict = {}
    messages: list[dict[str, str]] = []
    r1 = _turn(messages, answers, leg)
    state1 = r1.consultation_state
    runner.check("syndrome_recognized", state1.pathway_id == "lumbar_radiculopathy", state1.pathway_id)
    runner.check("not_unclassified_label", "boshqa nevrologik" not in state1.syndrome_label_uz.lower(), state1.syndrome_label_uz)
    runner.check("first_question", "?" in r1.patient_reply, r1.patient_reply[:120])
    pending1 = state1.pending_topic
    runner.check("has_pending_topic", bool(pending1), str(pending1))

    r2 = _turn(messages, answers, "Ha, oyoqqa tarqaladi")
    state2 = r2.consultation_state
    runner.check("session_id_stable", state2.pathway_id == "lumbar_radiculopathy", state2.pathway_id)
    runner.check("answer_recorded", pending1 in state2.answered_slugs, str(state2.answered_slugs))
    runner.check("no_duplicate_question", r2.patient_reply != r1.patient_reply or state2.pending_topic != pending1, pending1)

    # Greeting mid-consultation must resume, not restart
    r3 = _turn(messages, answers, "Salom")
    runner.check("greeting_resumes", "davom" in r3.patient_reply.lower() or "oxirgi" in r3.patient_reply.lower(), r3.patient_reply[:120])
    runner.check("pathway_after_greeting", r3.consultation_state.pathway_id == "lumbar_radiculopathy", r3.consultation_state.pathway_id)

    # Explicit new-complaint hint clarifies in-session — no state wipe
    before_slugs = list(r3.consultation_state.answered_slugs)
    r4 = _turn(messages, answers, "Yangi muammo haqida gapirmoqchiman")
    runner.check("topic_clarify_not_restart", len(r4.consultation_state.answered_slugs) >= len(before_slugs), str(r4.consultation_state.answered_slugs))
    runner.check("clarify_reply", "yangi muammo" in r4.patient_reply.lower(), r4.patient_reply[:120])

    # Engine integration — active DB session never auto-restarts on mid-turn message
    patient_id = upsert_user(telegram_id=9909001, username="arch_test", full_name="Arch Test")
    seed_default_location(patient_id)
    user_data: dict = {}
    t1 = process_consultation_turn(patient_id, leg, user_data=user_data)
    session = get_active_session(patient_id)
    runner.check("db_session_created", session is not None and t1.session_id == session.id, str(t1.session_id))
    sid_before = session.id if session else 0

    t2 = process_consultation_turn(patient_id, "Ha, beldan oyoqqa tarqaladi", user_data=user_data)
    session2 = get_active_session(patient_id)
    runner.check("same_session_after_turn", session2 is not None and session2.id == sid_before, f"{sid_before} -> {session2.id if session2 else None}")
    runner.check("still_collecting", t2.phase in {"collecting", "awaiting_help_choice"}, t2.phase)

    t3 = process_consultation_turn(patient_id, "Salom", user_data=user_data)
    session3 = get_active_session(patient_id)
    runner.check("greeting_keeps_session", session3 is not None and session3.id == sid_before, str(session3.id if session3 else None))

    # ConsultationState is sole authority in persisted answers
    loaded = ConsultationState.load(session3.answers if session3 else {})
    runner.check("state_in_answers", bool(session3 and session3.answers.get("consultation_state")), "")
    runner.check("state_pathway_persisted", loaded.pathway_id == "lumbar_radiculopathy", loaded.pathway_id)

    # Unrecognized complaint uses unclassified_neurology, not other_neurological label
    vague = process_consultation_intelligence_turn(
        user_message="Nimadir g'alati his qilyapman",
        session_messages=[{"role": "user", "content": "Nimadir g'alati his qilyapman"}],
        answers={},
    )
    runner.check(
        "vague_unclassified_pathway",
        vague.consultation_state.pathway_id in {"unclassified_neurology", "general_neurology", "functional_neurology"},
        vague.consultation_state.pathway_id,
    )
    runner.check(
        "vague_not_other_label",
        "boshqa nevrologik shikoyat" not in vague.consultation_state.syndrome_label_uz.lower(),
        vague.consultation_state.syndrome_label_uz,
    )

    print()
    print("=" * 72)
    print(f"CONSULTATION ARCHITECTURE v6: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Consultation architecture v6 OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
