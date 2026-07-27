"""Phase 5/6 — Consultation Intelligence Engine verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_phase_5_engine.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "phase5-engine-test"
os.environ["OPENAI_API_KEY"] = "phase5-engine-test"

sys.path.insert(0, str(ROOT))

from app.consultation_intelligence import (  # noqa: E402
    ENGINE_VERSION,
    ConsultationStage,
    ConsultationState,
    process_intelligence_turn,
)
from app.services.consultation_ai import run_intelligence_turn  # noqa: E402


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
    runner.check("engine_version", ENGINE_VERSION == "6.7.0", ENGINE_VERSION)

    known: dict = {}
    messages: list[dict[str, str]] = []
    text = "Chap oyoq og'riyapti"
    messages.append({"role": "user", "content": text})

    r1 = process_intelligence_turn(
        user_message=text,
        session_messages=messages,
        known_facts=known,
        topics_covered=[],
    )
    runner.check("recognizes_syndrome", r1.consultation_state.pathway_id == "lumbar_radiculopathy", r1.consultation_state.pathway_id)
    runner.check("not_generic", "boshqa nevrologik" not in r1.consultation_state.syndrome_label_uz.lower(), r1.consultation_state.syndrome_label_uz)
    runner.check("has_pending", bool(r1.consultation_state.pending_topic), r1.consultation_state.pending_topic)
    runner.check("first_reply", "?" in r1.patient_reply, r1.patient_reply[:100])
    runner.check("state_persisted", "consultation_state" in r1.known_facts, "")

    pending = r1.consultation_state.pending_topic
    messages.append({"role": "assistant", "content": r1.patient_reply})
    messages.append({"role": "user", "content": "Yo'q, bunday emas"})
    r2 = process_intelligence_turn(
        user_message="Yo'q, bunday emas",
        session_messages=messages,
        known_facts=r1.known_facts,
        topics_covered=r1.topics_covered,
    )
    runner.check("answered_recorded", pending in r2.consultation_state.answered_slugs, str(r2.consultation_state.answered_slugs))
    runner.check("no_duplicate_pending", r2.consultation_state.pending_topic != pending or r2.consultation_state.pending_topic is None, pending)
    runner.check("stage_collecting", r2.consultation_state.stage in {ConsultationStage.COLLECTING, ConsultationStage.AWAITING_HELP, ConsultationStage.CLOSURE}, r2.consultation_state.stage.value)

    state = ConsultationState.load(r2.known_facts)
    pathway = __import__("app.clinical_brain.clinical_pathways", fromlist=["get_pathway"]).get_pathway("lumbar_radiculopathy")
    state.answered_slugs = [n.topic_slug for n in pathway.nodes]  # type: ignore[union-attr]
    state.pathway_locked = True
    state.pathway_id = "lumbar_radiculopathy"
    state.syndrome_label_uz = "Lumbosakral radikulopatiya"
    state.persist_into(known)
    r3 = process_intelligence_turn(
        user_message="ha",
        session_messages=messages,
        known_facts=known,
        topics_covered=state.answered_slugs,
    )
    runner.check("closure_ready", r3.ready_for_help_menu or r3.consultation_state.stage == ConsultationStage.AWAITING_HELP, r3.consultation_state.stage.value)

    mig = process_intelligence_turn(
        user_message="Migrenim bor, chakka og'riyapti",
        session_messages=[{"role": "user", "content": "Migrenim bor, chakka og'riyapti"}],
        known_facts={},
        topics_covered=[],
    )
    runner.check("migraine_pathway", mig.consultation_state.pathway_id == "migraine", mig.consultation_state.pathway_id)

    wrapped = run_intelligence_turn(
        user_message="Yuz qiyshayapti",
        session_messages=[{"role": "user", "content": "Yuz qiyshayapti"}],
        known_facts={},
        topics_covered=[],
        prior_complaints=[],
    )
    runner.check("ai_wrapper", "?" in wrapped.patient_reply, wrapped.patient_reply[:80])
    runner.check(
        "wrapper_syndrome",
        "bell" in wrapped.internal_reasoning.possible_neurological_causes[0].lower()
        if wrapped.internal_reasoning.possible_neurological_causes
        else False
        or "yuz" in wrapped.patient_reply.lower(),
        str(wrapped.internal_reasoning.possible_neurological_causes),
    )

    print()
    print("=" * 72)
    print(f"PHASE 5 CONSULTATION ENGINE: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Consultation Intelligence Engine v6 OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
