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
    runner.check("engine_version_v6", ENGINE_VERSION == "6.6.0", ENGINE_VERSION)

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

    # Dynamic differential updates after each answer
    runner.check(
        "differential_populated",
        len(state2.differential) >= 1,
        str(state2.differential[:2]),
    )
    runner.check(
        "clinical_assessment_present",
        bool(state2.clinical_assessment.get("leading_diagnosis")),
        str(state2.clinical_assessment),
    )
    runner.check(
        "closure_not_ready_early",
        not state2.clinical_assessment.get("closure_readiness", {}).get("evidence_sufficient", True),
        str(state2.clinical_assessment.get("closure_readiness")),
    )
    runner.check(
        "exclusion_status_tracked",
        any(d.get("exclusion_status") for d in state2.differential),
        str(state2.differential[:2]),
    )
    runner.check(
        "differential_probabilities_sum",
        sum(d.get("probability_pct", 0) for d in state2.differential) > 90,
        str([d.get("probability_pct") for d in state2.differential]),
    )

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

    # Full pathway — must not close before all required nodes are answered
    from app.clinical_brain.clinical_pathways import get_pathway

    spine_answers: dict = {}
    spine_msgs: list[dict[str, str]] = []
    spine_open = "Belim og'riyapti"
    sr = _turn(spine_msgs, spine_answers, spine_open)
    pathway = get_pathway(sr.consultation_state.pathway_id)
    required_nodes = [n for n in pathway.nodes if n.required] if pathway else []
    for i in range(max(len(required_nodes) - 1, 1)):
        if sr.ready_for_help_menu:
            break
        ans = f"3 kun oldin, javob {i}"
        sr = _turn(spine_msgs, spine_answers, ans)
    runner.check(
        "no_early_closure",
        not sr.ready_for_help_menu,
        f"answered={sr.consultation_state.answered_slugs}",
    )

    # Advice question during collecting — continue consultation, not help menu
    adv_answers: dict = {}
    adv_msgs: list[dict[str, str]] = []
    _turn(adv_msgs, adv_answers, leg)
    adv = _turn(adv_msgs, adv_answers, "Nima qilsam bo'ladi?")
    runner.check(
        "advice_no_help_menu",
        "Keyingi qadamda sizga qanday yordam beray?" not in adv.patient_reply,
        adv.patient_reply[:120],
    )
    runner.check(
        "advice_continues_consultation",
        "ehtimoliy yo'nalish" in adv.patient_reply.lower() or "radikulopatiya" in adv.patient_reply.lower(),
        adv.patient_reply[:160],
    )
    runner.check(
        "advice_not_generic_wait",
        "avval muhim savollarga javob olishim kerak" not in adv.patient_reply.lower(),
        adv.patient_reply[:160],
    )

    # Advice patterns — nima maslahat, qanday davolansam
    adv2 = _turn(adv_msgs, adv_answers, "Nima maslahat berasan?")
    runner.check(
        "advice_nima_maslahat",
        "ehtimoliy" in adv2.patient_reply.lower() or "radikulopatiya" in adv2.patient_reply.lower(),
        adv2.patient_reply[:160],
    )
    adv3 = _turn(adv_msgs, adv_answers, "Qanday davolansam bo'ladi?")
    runner.check(
        "advice_qanday_davolansam",
        "shifokor" in adv3.patient_reply.lower() or "radikulopatiya" in adv3.patient_reply.lower(),
        adv3.patient_reply[:160],
    )

    # New symptom during consultation — merge headache, ask follow-up
    ns_answers: dict = {}
    ns_msgs: list[dict[str, str]] = []
    _turn(ns_msgs, ns_answers, leg)
    ns = _turn(ns_msgs, ns_answers, "Boshim ham og'riyapti")
    runner.check(
        "new_symptom_merged",
        any(s.get("category") == "headache" for s in ns.consultation_state.secondary_symptoms),
        str(ns.consultation_state.secondary_symptoms),
    )
    runner.check(
        "new_symptom_followup",
        "bosh" in ns.patient_reply.lower() and "?" in ns.patient_reply,
        ns.patient_reply[:160],
    )
    runner.check(
        "new_symptom_no_restart",
        ns.consultation_state.pathway_id == "lumbar_radiculopathy",
        ns.consultation_state.pathway_id,
    )

    # Leg weakness alone on cauda screen must NOT trigger emergency
    em_answers: dict = {}
    em_msgs: list[dict[str, str]] = []
    _turn(em_msgs, em_answers, leg)
    em = _turn(em_msgs, em_answers, "Ha")
    runner.check(
        "leg_weakness_not_stroke_emergency",
        not em.suggests_emergency,
        str(em.emergency_flags),
    )
    runner.check(
        "leg_weakness_stays_collecting",
        em.consultation_state.emergency_status.value in {"none", "suspected"},
        em.consultation_state.emergency_status.value,
    )

    # Obvious cauda red flags must trigger emergency
    cauda_answers: dict = {}
    cauda_msgs: list[dict[str, str]] = []
    _turn(cauda_msgs, cauda_answers, "Belim og'riyapti, ikki oyoq kuchsiz, siydik tutolmayapti")
    cauda = _turn(cauda_msgs, cauda_answers, "Ha, ikkala oyoq ham kuchsiz, siydik chiqmayapti")
    runner.check(
        "cauda_triggers_emergency",
        cauda.suggests_emergency or cauda.consultation_state.emergency_status.value == "confirmed",
        str(cauda.emergency_flags),
    )

    # Patient-facing closure must not expose internal topic slugs
    slug_answers: dict = {}
    slug_msgs: list[dict[str, str]] = []
    slug_state = ConsultationState.load({})
    slug_state.pathway_id = "lumbar_spine"
    slug_state.pathway_locked = True
    slug_state.syndrome_label_uz = "Lumbal umurtqa pog'onasi sindromi"
    slug_state.dominant_complaint = "Bel og'rig'i"
    slug_state.opening_complaint = "Belim og'riyapti"
    slug_state.record_answer("opening_complaint", "Belim og'riyapti", "Belim og'riyapti")
    for node in get_pathway("lumbar_spine").nodes:
        slug_state.record_answer(node.topic_slug, "ha", "ha")
    slug_state.persist_into(slug_answers)
    slug_closed = process_consultation_intelligence_turn(
        user_message="tayyor",
        session_messages=[{"role": "user", "content": "tayyor"}],
        answers=slug_answers,
    )
    runner.check(
        "no_internal_slug_in_reply",
        "lumbar_spine" not in slug_closed.patient_reply.lower(),
        slug_closed.patient_reply[:200],
    )

    # Every registered clinical pathway must have a disease-specific reasoning
    # profile (mandatory questions, red flags, differential, investigations,
    # treatment, referral) — not the generic single-diagnosis fallback.
    from app.clinical_brain.clinical_pathways import all_pathways
    from app.consultation_intelligence.pathway_knowledge import get_reasoning_profile
    from app.consultation_intelligence.differential_engine import update_differential, build_clinical_assessment
    from app.consultation_intelligence.closure_verifier import assess_closure_readiness

    for pw in all_pathways():
        profile = get_reasoning_profile(pw.id)
        runner.check(f"reasoning_profile_exists:{pw.id}", profile is not None, pw.id)
        if profile is None:
            continue
        runner.check(
            f"reasoning_profile_has_diagnoses:{pw.id}",
            len(profile.diagnoses) >= 2,
            f"{len(profile.diagnoses)} diagnoses",
        )

        probe_state = ConsultationState.load({})
        probe_state.pathway_id = pw.id
        probe_facts = {node.topic_slug: "positive" for node in pw.nodes}
        probe_differential = update_differential(probe_state, probe_facts)
        total_pct = sum(float(d.get("probability_pct") or 0) for d in probe_differential)
        runner.check(
            f"differential_sums_to_100:{pw.id}",
            99.0 <= total_pct <= 101.0,
            f"total={total_pct}",
        )
        probe_state.differential = probe_differential
        probe_state.clinical_assessment = build_clinical_assessment(probe_state, probe_differential)
        probe_state.answered_slugs = [n.topic_slug for n in pw.nodes]
        readiness = assess_closure_readiness(probe_state)
        runner.check(
            f"closure_readiness_computable:{pw.id}",
            isinstance(readiness.ready, bool),
            str(readiness.checks),
        )

    # Adaptive question ordering — the next question depends on the live
    # differential, not a fixed script. Positive vs negative central screen
    # must flip the leading diagnosis for the same pathway/onset.
    from app.consultation_intelligence.decision_engine import DecisionEngine

    engine = DecisionEngine()

    def _probe(pathway_id: str, extra_answers: dict[str, tuple[str, str]]) -> ConsultationState:
        st = ConsultationState.load({})
        st.pathway_id = pathway_id
        st.pathway_locked = True
        st.record_answer("opening_complaint", "yuzim qiyshaydi", "yuzim qiyshaydi")
        for slug, (raw, parsed) in extra_answers.items():
            st.record_answer(slug, raw, parsed)
        st.differential = update_differential(st, st.fact_map())
        st.clinical_assessment = build_clinical_assessment(st, st.differential)
        return st

    fn_pos = _probe(
        "facial_nerve",
        {
            "facial_nerve_central_screen": ("ha, qo'lim ham kuchsiz", "positive"),
            "facial_nerve_onset": ("birdan", "sudden_onset"),
        },
    )
    fn_neg = _probe(
        "facial_nerve",
        {
            "facial_nerve_central_screen": ("yo'q", "negative"),
            "facial_nerve_onset": ("birdan", "sudden_onset"),
        },
    )
    runner.check(
        "adaptive_differential_flips_with_evidence",
        fn_pos.differential[0]["name"] != fn_neg.differential[0]["name"],
        f"{fn_pos.differential[0]['name']} vs {fn_neg.differential[0]['name']}",
    )
    runner.check(
        "adaptive_central_positive_flags_stroke_mimic",
        "sentral" in fn_pos.differential[0]["name"].lower() or "insult" in fn_pos.differential[0]["name"].lower(),
        fn_pos.differential[0]["name"],
    )

    # Variable-length consultation — a clear-cut presentation should close with
    # fewer questions (skipping the optional low-yield node) than an ambiguous
    # one that genuinely needs more evidence before concluding.
    def _run_vestibular(answers_pool: dict[str, tuple[str, str]]) -> int:
        st = ConsultationState.load({})
        st.pathway_id = "vestibular"
        st.pathway_locked = True
        st.record_answer("opening_complaint", "boshim aylanadi", "boshim aylanadi")
        for turns in range(10):
            st.differential = update_differential(st, st.fact_map())
            st.clinical_assessment = build_clinical_assessment(st, st.differential)
            decision = engine.decide(st)
            if decision.action == "closure":
                return turns
            raw, parsed = answers_pool.get(decision.topic_slug, ("ha", "positive"))
            st.record_answer(decision.topic_slug, raw, parsed)
        return 10

    clear_cut_turns = _run_vestibular(
        {
            "vestibular_central_screen": ("yo'q", "negative"),
            "vestibular_timing": ("bir necha soniya", "bir necha soniya"),
            "vestibular_position": ("ha, boshni burganda", "positive"),
            "vestibular_hearing": ("yo'q", "negative"),
        }
    )
    ambiguous_turns = _run_vestibular(
        {
            "vestibular_central_screen": ("yo'q", "negative"),
            "vestibular_timing": ("bir necha soat", "bir necha soat"),
            "vestibular_position": ("aniq emas", "aniq emas"),
            "vestibular_hearing": ("biroz eshitish pasaygan", "biroz eshitish pasaygan"),
            "vestibular_associated": ("qusish bor", "qusish bor"),
        }
    )
    runner.check(
        "adaptive_length_clear_case_shorter",
        clear_cut_turns <= ambiguous_turns,
        f"clear={clear_cut_turns} ambiguous={ambiguous_turns}",
    )
    runner.check(
        "adaptive_length_skips_optional_when_confident",
        clear_cut_turns < 5,
        f"clear_cut_turns={clear_cut_turns}",
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
