"""AI Neurology Assistant — GPT-driven consultation orchestration."""

from __future__ import annotations

import logging
from typing import Any

from app.domain.consultation import ConsultationSession, ConsultationTurnResult
from app.repositories.consultation_repository import (
    create_session,
    get_active_session,
    update_session,
)
from app.repositories.conversation_repository import get_last_messages, get_or_create_active_conversation
from app.services.consultation_ai import (
    COMPLAINT_SWITCH_PROMPT,
    GREETING_RESUME_PROMPT,
    HELP_MENU_TEXT,
    append_legal_disclaimer,
    build_help_menu_reply,
    parse_complaint_clarification,
    parse_help_choice,
    parse_session_choice,
    run_help_followup_turn,
    run_intelligence_turn,
    run_medical_turn,
    run_conversation_intent_analysis,  # deprecated in v6 routing; kept for test mocks
)
run_neurology_turn = run_intelligence_turn  # production: code-driven consultation engine v6
from app.consultation_intelligence.message_intent import is_advice_question
from app.consultation_intelligence.state import ConsultationState
from app.clinical_brain.clinical_pathways.recognition import resolve_complaint_category
from app.services.consultation_classifier import classify_complaint, complaint_label
from app.medical_brain.router import is_medical_consultation_trigger, route_medical_specialties
from app.domain.medical import specialty_label
from app.services.consultation_red_flags import (
    build_consultation_emergency_response,
    detect_consultation_red_flags,
)
from app.services.doctor_visit_service import resolve_active_visit_id
from app.services.emr_service import edit_visit, get_visit_history
from app.services.location_profile import is_medical_complaint
from app.services.appointment_dates import clinic_today_iso
from app.repositories.emr_repository import get_emr_visit

logger = logging.getLogger("doctor_boysunov.consultation_engine")

CONSULTATION_SESSION_KEY = "consultation_session_id"

_EXPLICIT_SYMPTOM_HINTS = (
    "og'ri", "ogri", "og‘ri", "uvish", "titro", "titray", "qaltir", "bosh", "bel",
    "bo'yin", "boyin", "hush", "insult", "falaj", "depres", "xavotir", "uyqu",
    "uxlam", "xotira", "aylan", "vertigo", "shikoyat", "symptom", "pain", "hurt",
    "ache", "numb", "weak",
)


def is_consultation_trigger(message: str) -> bool:
    if not is_medical_complaint(message):
        return False
    if is_medical_consultation_trigger(message):
        return True
    category = classify_complaint(message)
    if category != "other_neurological":
        return True
    normalized = message.strip().lower()
    return any(hint in normalized for hint in _EXPLICIT_SYMPTOM_HINTS)


def should_use_consultation_engine(
    patient_id: int,
    message: str,
    user_data: dict[str, Any] | None,
) -> bool:
    if get_active_session(patient_id) is not None:
        return True
    if user_data and user_data.get(CONSULTATION_SESSION_KEY):
        return True
    return is_consultation_trigger(message)


def _session_state(answers: dict[str, Any]) -> dict[str, Any]:
    known = dict(answers.get("known_facts") or {})
    return {
        "known_facts": known,
        "topics_covered": list(answers.get("topics_covered") or answers.get("topics_covered_list") or []),
        "session_messages": list(answers.get("session_messages") or []),
        "disclaimer_shown": bool(answers.get("disclaimer_shown")),
        "help_choice": answers.get("help_choice"),
        "pending_message": answers.get("pending_message"),
        "primary_specialty": answers.get("primary_specialty"),
        "secondary_specialties": list(answers.get("secondary_specialties") or []),
    }


def _merge_state(answers: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    merged = dict(answers)
    merged["known_facts"] = state["known_facts"]
    merged["topics_covered"] = state["topics_covered"]
    merged["session_messages"] = state["session_messages"]
    merged["disclaimer_shown"] = state["disclaimer_shown"]
    merged["help_choice"] = state["help_choice"]
    merged["pending_message"] = state.get("pending_message")
    merged["primary_specialty"] = state.get("primary_specialty")
    merged["secondary_specialties"] = state.get("secondary_specialties", [])
    cs = state["known_facts"].get("consultation_state") if isinstance(state.get("known_facts"), dict) else None
    if cs:
        merged["consultation_state"] = cs
    return merged


def process_consultation_turn(
    patient_id: int,
    message: str,
    *,
    user_data: dict[str, Any] | None = None,
) -> ConsultationTurnResult:
    text = (message or "").strip()
    if not text:
        return ConsultationTurnResult(
            reply="Iltimos, shikoyatingizni qisqacha yozing.",
            phase="collecting",
            used_consultation_engine=True,
        )

    global_flags = detect_consultation_red_flags(text)
    if global_flags and _is_immediate_emergency(text, global_flags):
        visit_id = resolve_active_visit_id(patient_id)
        _persist_emergency(patient_id, visit_id, text, global_flags)
        return ConsultationTurnResult(
            reply=build_consultation_emergency_response(global_flags),
            phase="emergency",
            emergency=True,
            used_consultation_engine=True,
        )

    session = get_active_session(patient_id)
    if session is None:
        return _start_new_session(patient_id, text, user_data=user_data)

    if session.phase == "awaiting_session_choice":
        return _handle_session_choice(session, text, user_data=user_data)

    if session.phase == "awaiting_complaint_clarification":
        return _handle_complaint_clarification(session, text, user_data=user_data)

    if session.phase == "awaiting_help_choice":
        return _route_active_session(session, text, user_data=user_data, allow_help_choice=True)

    return _route_active_session(session, text, user_data=user_data, allow_help_choice=False)


def _route_active_session(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
    allow_help_choice: bool,
) -> ConsultationTurnResult:
    state = _session_state(session.answers)
    state["session_messages"].append({"role": "user", "content": text})

    if allow_help_choice:
        choice = parse_help_choice(text)
        if choice is not None:
            state["session_messages"].pop()
            return _handle_help_choice(session, text, user_data=user_data)

    # Active consultations never auto-restart — controller handles greetings and topic changes.
    return _continue_session(session, text, user_data=user_data, state=state)


def _prompt_session_choice(
    session: ConsultationSession,
    state: dict[str, Any],
    text: str,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    state["pending_message"] = text
    reply = GREETING_RESUME_PROMPT
    state["session_messages"].append({"role": "assistant", "content": reply})
    update_session(
        session.id,
        phase="awaiting_session_choice",
        answers=_merge_state(session.answers, state),
    )
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id
    return ConsultationTurnResult(
        reply=reply,
        phase="awaiting_session_choice",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _prompt_complaint_clarification(
    session: ConsultationSession,
    state: dict[str, Any],
    text: str,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    state["pending_message"] = text
    reply = COMPLAINT_SWITCH_PROMPT
    state["session_messages"].append({"role": "assistant", "content": reply})
    update_session(
        session.id,
        phase="awaiting_complaint_clarification",
        answers=_merge_state(session.answers, state),
    )
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id
    return ConsultationTurnResult(
        reply=reply,
        phase="awaiting_complaint_clarification",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _handle_session_choice(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    choice = parse_session_choice(text)
    state = _session_state(session.answers)
    state["session_messages"].append({"role": "user", "content": text})

    if choice == "new":
        pending = state.pop("pending_message", None)
        _complete_session(session, user_data)
        if pending and is_medical_complaint(pending):
            return _start_new_session(session.patient_id, pending, user_data=user_data)
        return ConsultationTurnResult(
            reply="Yaxshi. Yangi muammoingizni qisqacha yozing.",
            phase="collecting",
            used_consultation_engine=True,
        )

    if choice == "continue":
        pending = state.get("pending_message")
        state["pending_message"] = None
        update_session(
            session.id,
            phase="collecting",
            answers=_merge_state(session.answers, state),
        )
        last_user = _last_non_greeting_user_message(state["session_messages"])
        resume_text = last_user if pending and not is_medical_complaint(pending) else (pending or text)
        if not resume_text or not is_medical_complaint(resume_text):
            reply = "Yaxshi, davom etamiz. Oldingi savolimga javob bering yoki holatingizni davom ettiring."
            state["session_messages"].append({"role": "assistant", "content": reply})
            update_session(session.id, answers=_merge_state(session.answers, state))
            return ConsultationTurnResult(
                reply=reply,
                phase="collecting",
                session_id=session.id,
                used_consultation_engine=True,
            )
        return _continue_session(session, resume_text, user_data=user_data, state=state)

    reply = f"Iltimos, tanlang:\n{GREETING_RESUME_PROMPT}"
    return ConsultationTurnResult(
        reply=reply,
        phase="awaiting_session_choice",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _handle_complaint_clarification(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    choice = parse_complaint_clarification(text)
    state = _session_state(session.answers)
    state["session_messages"].append({"role": "user", "content": text})
    pending = state.get("pending_message") or text

    if choice == "new_complaint":
        _complete_session(session, user_data)
        return _start_new_session(session.patient_id, pending, user_data=user_data)

    if choice == "continue_previous":
        state["pending_message"] = None
        update_session(
            session.id,
            phase="collecting",
            answers=_merge_state(session.answers, state),
        )
        return _continue_session(session, pending, user_data=user_data, state=state)

    reply = f"Iltimos, aniqlang:\n{COMPLAINT_SWITCH_PROMPT}"
    return ConsultationTurnResult(
        reply=reply,
        phase="awaiting_complaint_clarification",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _last_non_greeting_user_message(messages: list[dict[str, str]]) -> str | None:
    greeting_words = ("salom", "assalom", "hello", "hi")
    for item in reversed(messages):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        lowered = content.lower()
        if content and not any(word in lowered for word in greeting_words):
            return content
    return None


def _complete_session(session: ConsultationSession, user_data: dict[str, Any] | None) -> None:
    update_session(session.id, phase="complete")
    if user_data is not None:
        user_data.pop(CONSULTATION_SESSION_KEY, None)


def _prior_complaints(patient_id: int) -> list[str]:
    history = get_visit_history(patient_id)
    complaints = [
        item["complaint"]
        for item in history.get("previous_complaints", [])
        if item.get("complaint")
    ]
    conversation_id = get_or_create_active_conversation(patient_id)
    for msg in get_last_messages(conversation_id, limit=20):
        if msg.get("role") == "user" and is_medical_complaint(msg.get("content", "")):
            complaints.append(msg["content"][:200])
    return complaints[-8:]


def _start_new_session(
    patient_id: int,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    category = resolve_complaint_category(text, category_hint=classify_complaint(text))
    routing = route_medical_specialties(text)
    visit_id = resolve_active_visit_id(patient_id)
    session = create_session(patient_id, visit_id, category)
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id

    state = {
        "known_facts": {"opening_complaint": text},
        "topics_covered": ["opening_complaint"],
        "session_messages": [{"role": "user", "content": text}],
        "disclaimer_shown": False,
        "help_choice": None,
        "pending_message": None,
        "primary_specialty": routing.primary,
        "secondary_specialties": routing.secondary,
    }
    update_session(session.id, answers=_merge_state({"chief_complaint_text": text}, state))
    complaint_display = specialty_label(routing.primary)
    if routing.secondary:
        complaint_display += " + " + " + ".join(specialty_label(s) for s in routing.secondary)
    edit_visit(patient_id, visit_id, main_complaint=complaint_display)

    gpt = run_neurology_turn(
        category=category,
        user_message=text,
        session_messages=state["session_messages"],
        known_facts=state["known_facts"],
        topics_covered=state["topics_covered"],
        prior_complaints=_prior_complaints(patient_id),
        patient_id=patient_id,
        visit_history=get_visit_history(patient_id),
        append_disclaimer=True,
        primary_specialty=routing.primary,
        secondary_specialties=routing.secondary,
    )

    if gpt.suggests_emergency:
        flags = detect_consultation_red_flags(text) or ["gpt_urgent_assessment"]
        _persist_emergency(patient_id, visit_id, text, flags)
        if user_data is not None:
            user_data.pop(CONSULTATION_SESSION_KEY, None)
        return ConsultationTurnResult(
            reply=build_consultation_emergency_response(flags),
            phase="emergency",
            emergency=True,
            used_consultation_engine=True,
        )

    reply, disclaimer_shown = append_legal_disclaimer(gpt.patient_reply, already_appended=False)
    state["session_messages"].append({"role": "assistant", "content": reply})
    state["known_facts"].update(gpt.known_facts)
    state["topics_covered"] = _merge_topics(state["topics_covered"], gpt.topics_covered)
    state["primary_specialty"] = gpt.primary_specialty
    state["secondary_specialties"] = gpt.secondary_specialties
    state["disclaimer_shown"] = disclaimer_shown

    _persist_doctor_emr(
        patient_id, visit_id, gpt.doctor_emr.to_dict(), gpt.session_summary
    )
    update_session(
        session.id,
        answers=_merge_state({"chief_complaint_text": text}, state),
        asked_question_ids=state["topics_covered"],
        summary=gpt.session_summary,
    )

    logger.info("consultation_started patient_id=%s session_id=%s category=%s", patient_id, session.id, category)
    return ConsultationTurnResult(
        reply=reply,
        phase="collecting",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _continue_session(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> ConsultationTurnResult:
    state = state or _session_state(session.answers)
    if not state["session_messages"] or state["session_messages"][-1].get("content") != text:
        state["session_messages"].append({"role": "user", "content": text})

    gpt = run_neurology_turn(
        category=session.complaint_category,
        user_message=text,
        session_messages=state["session_messages"],
        known_facts=state["known_facts"],
        topics_covered=state["topics_covered"],
        prior_complaints=_prior_complaints(session.patient_id),
        patient_id=session.patient_id,
        visit_history=get_visit_history(session.patient_id),
        append_disclaimer=not state["disclaimer_shown"],
        primary_specialty=state.get("primary_specialty"),
        secondary_specialties=state.get("secondary_specialties"),
    )

    if gpt.suggests_emergency:
        flags = detect_consultation_red_flags(text) or ["gpt_urgent_assessment"]
        _persist_emergency(session.patient_id, session.visit_id, text, flags)
        update_session(session.id, phase="emergency", answers=_merge_state(session.answers, state))
        if user_data is not None:
            user_data.pop(CONSULTATION_SESSION_KEY, None)
        return ConsultationTurnResult(
            reply=build_consultation_emergency_response(flags),
            phase="emergency",
            session_id=session.id,
            emergency=True,
            used_consultation_engine=True,
        )

    state["known_facts"].update(gpt.known_facts)
    state["topics_covered"] = _merge_topics(state["topics_covered"], gpt.topics_covered)
    state["primary_specialty"] = gpt.primary_specialty
    state["secondary_specialties"] = gpt.secondary_specialties
    _persist_doctor_emr(
        session.patient_id,
        session.visit_id,
        gpt.doctor_emr.to_dict(),
        gpt.session_summary,
    )

    if gpt.ready_for_help_menu:
        reply = build_help_menu_reply(gpt.brief_summary_for_patient)
        state["session_messages"].append({"role": "assistant", "content": reply})
        summary = dict(gpt.session_summary)
        summary["patient_summary"] = gpt.brief_summary_for_patient
        cs = ConsultationState.load(state["known_facts"])
        cs.help_menu_shown = True
        cs.persist_into(state["known_facts"])
        update_session(
            session.id,
            phase="awaiting_help_choice",
            answers=_merge_state(session.answers, state),
            asked_question_ids=state["topics_covered"],
            summary=summary,
        )
        if user_data is not None:
            user_data[CONSULTATION_SESSION_KEY] = session.id
        return ConsultationTurnResult(
            reply=reply,
            phase="awaiting_help_choice",
            session_id=session.id,
            used_consultation_engine=True,
        )

    reply, state["disclaimer_shown"] = append_legal_disclaimer(
        gpt.patient_reply,
        already_appended=state["disclaimer_shown"],
    )
    state["session_messages"].append({"role": "assistant", "content": reply})
    update_session(
        session.id,
        answers=_merge_state(session.answers, state),
        asked_question_ids=state["topics_covered"],
        summary=gpt.session_summary,
    )
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id

    return ConsultationTurnResult(
        reply=reply,
        phase="collecting",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _handle_help_choice(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    choice = parse_help_choice(text)
    state = _session_state(session.answers)
    state["session_messages"].append({"role": "user", "content": text})

    if choice is None and is_advice_question(text):
        update_session(
            session.id,
            phase="collecting",
            answers=_merge_state(session.answers, state),
        )
        return _continue_session(session, text, user_data=user_data, state=state)

    if choice == "continue":
        state["session_messages"].pop()
        state["help_choice"] = "continue"
        update_session(
            session.id,
            phase="collecting",
            answers=_merge_state(session.answers, state),
        )
        resume_text = _last_non_greeting_user_message(state["session_messages"]) or ""
        return _continue_session(
            session,
            resume_text or "davom etamiz",
            user_data=user_data,
            state=state,
        )

    if choice in {"online", "clinic"}:
        state["help_choice"] = choice
        reply = run_help_followup_turn(
            category=session.complaint_category,
            choice=choice,
            session_messages=state["session_messages"],
            known_facts=state["known_facts"],
        )
        cs = ConsultationState.load(state["known_facts"])
        cs.help_menu_shown = True
        cs.persist_into(state["known_facts"])
        state["known_facts"] = dict(state["known_facts"])
        state["session_messages"].append({"role": "assistant", "content": reply})
        update_session(
            session.id,
            phase="collecting",
            answers=_merge_state(session.answers, state),
            summary=session.summary,
        )
        if user_data is not None:
            user_data[CONSULTATION_SESSION_KEY] = session.id
        return ConsultationTurnResult(
            reply=reply,
            phase="collecting",
            session_id=session.id,
            used_consultation_engine=True,
        )

    reply = f"Iltimos, tanlang:\n{HELP_MENU_TEXT}"
    return ConsultationTurnResult(
        reply=reply,
        phase="awaiting_help_choice",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _merge_topics(existing: list[str], new_items: list[str]) -> list[str]:
    merged = list(existing)
    for item in new_items:
        if item and item not in merged:
            merged.append(item)
    return merged


def _persist_doctor_emr(
    patient_id: int,
    visit_id: int,
    emr: dict[str, Any],
    summary: dict[str, Any] | None = None,
) -> None:
    from app.clinical_brain.types import ClinicalBrainInternal, DoctorEmrUpdate
    from app.repositories.emr_repository import get_emr_visit
    from app.services.consultation_ai import InternalReasoning
    from app.services.emr_ai_service import save_ai_assessment
    from app.services.emr_service import edit_visit

    summary = summary or {}
    save_ai_assessment(
        visit_id,
        doctor_emr=emr,
        medical_brain=summary.get("medical_brain") or summary.get("clinical_brain"),
        primary_specialty=summary.get("primary_specialty"),
        secondary_specialties=summary.get("secondary_specialties"),
        internal_reasoning=summary.get("internal_reasoning"),
    )

    doctor = DoctorEmrUpdate.from_dict(emr)
    brain_data = summary.get("medical_brain") or summary.get("clinical_brain")
    internal_brain = (
        ClinicalBrainInternal.from_dict(brain_data)
        if isinstance(brain_data, dict)
        else None
    )
    block = doctor.format_emr_block(internal_brain)
    reasoning_dict = summary.get("internal_reasoning")
    if isinstance(reasoning_dict, dict):
        block = f"{block}\n\n{InternalReasoning.from_dict(reasoning_dict).format_emr_reasoning()}"

    closure_raw = summary.get("consultation_closure")
    if isinstance(closure_raw, dict) and closure_raw:
        from app.clinical_brain.senior_neurologist import ConsultationClosureSummary, format_closure_emr_block

        block = f"{block}\n\n{format_closure_emr_block(ConsultationClosureSummary.from_dict(closure_raw))}"

    visit = get_emr_visit(visit_id)
    existing = (visit or {}).get("notes") or ""
    if block.strip() and block.strip() not in existing:
        merged = f"{existing}\n\n{block}".strip() if existing else block
        edit_visit(patient_id, visit_id, notes=merged)


def _persist_emergency(patient_id: int, visit_id: int, text: str, flags: list[str]) -> None:
    note = (
        f"SHOSHILINCH: {', '.join(flags)}\n"
        f"Bemor xabari: {text.strip()}\n"
        f"Sana: {clinic_today_iso()}"
    )
    visit = get_emr_visit(visit_id)
    existing = (visit or {}).get("notes") or ""
    merged = f"{existing}\n{note}".strip() if existing else note
    edit_visit(patient_id, visit_id, notes=merged)


def _is_immediate_emergency(text: str, flags: list[str]) -> bool:
    lowered = text.lower()
    acute = (
        "stroke" in flags
        or "consciousness" in flags
        or "breathing" in flags
        or "seizure" in flags
        or "insult" in lowered
        or "falaj" in lowered
        or "hushdan" in lowered
        or "103" in lowered
    )
    return acute
