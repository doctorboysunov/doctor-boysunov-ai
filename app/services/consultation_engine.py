"""Professional Medical Consultation Engine — structured one-question-at-a-time intake."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.consultation import ConsultationSession, ConsultationTurnResult
from app.repositories.consultation_repository import (
    create_session,
    get_active_session,
    update_session,
)
from app.repositories.emr_repository import get_emr_visit
from app.services.appointment_dates import clinic_today_iso
from app.services.clinic_locator_service import recommend_clinic_for_patient
from app.services.consultation_classifier import classify_complaint, complaint_label
from app.services.consultation_question_trees import (
    get_question_by_id,
    has_enough_information,
    select_next_question,
)
from app.services.consultation_red_flags import (
    build_consultation_emergency_response,
    check_answer_red_flag,
    detect_consultation_red_flags,
)
from app.services.consultation_summary import generate_consultation_summary
from app.services.doctor_visit_service import resolve_active_visit_id
from app.services.emr_service import edit_visit
from app.services.location_profile import is_medical_complaint

logger = logging.getLogger("doctor_boysunov.consultation_engine")

CONSULTATION_SESSION_KEY = "consultation_session_id"

_EXPLICIT_SYMPTOM_HINTS = (
    "og'ri",
    "ogri",
    "og‘ri",
    "uvish",
    "titro",
    "titray",
    "qaltir",
    "bosh",
    "bel",
    "bo'yin",
    "boyin",
    "ko'krak",
    "qorin",
    "hush",
    "insult",
    "falaj",
    "depres",
    "xavotir",
    "uyqu",
    "uxlam",
    "xotira",
    "aylan",
    "vertigo",
    "shikoyat",
    "symptom",
    "pain",
    "hurt",
    "ache",
    "numb",
    "weak",
)


def is_consultation_trigger(message: str) -> bool:
    """True when message should start structured consultation (not general chat)."""
    if not is_medical_complaint(message):
        return False
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
        reply = build_consultation_emergency_response(global_flags)
        return ConsultationTurnResult(
            reply=reply,
            phase="emergency",
            emergency=True,
            used_consultation_engine=True,
        )

    session = get_active_session(patient_id)
    if session is None:
        return _start_new_session(patient_id, text, user_data=user_data)

    if session.phase == "complete":
        if is_consultation_trigger(text):
            return _start_new_session(patient_id, text, user_data=user_data)
        return ConsultationTurnResult(
            reply=(
                "Oldingi konsultatsiya yakunlangan. Yangi shikoyat bo'lsa, "
                "batafsil yozing — yangi konsultatsiya boshlayman."
            ),
            phase="complete",
            session_id=session.id,
            used_consultation_engine=True,
            completed=True,
        )

    return _continue_session(session, text, user_data=user_data)


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
    return acute or len(flags) >= 2


def _start_new_session(
    patient_id: int,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    category = classify_complaint(text)
    visit_id = resolve_active_visit_id(patient_id)

    first_question = select_next_question(category, set(), {})
    if first_question is None:
        return ConsultationTurnResult(
            reply="Shikoyatingizni qayta yozing, iltimos.",
            phase="collecting",
            used_consultation_engine=True,
        )

    session = create_session(
        patient_id,
        visit_id,
        category,
        current_question_id=first_question.id,
    )
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id

    initial_answers = {"chief_complaint_text": text}
    update_session(session.id, answers=initial_answers)
    _persist_answer_to_emr(patient_id, visit_id, "chief_complaint", text)
    edit_visit(
        patient_id,
        visit_id,
        main_complaint=complaint_label(category),
    )

    intro = (
        f"Tushundim — {complaint_label(category)} bo'yicha konsultatsiya boshlaymiz.\n"
        "Bir vaqtning o'zida faqat bitta muhim savol beraman.\n\n"
    )
    logger.info(
        "consultation_started patient_id=%s session_id=%s category=%s",
        patient_id,
        session.id,
        category,
    )
    return ConsultationTurnResult(
        reply=intro + first_question.text,
        phase="collecting",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _continue_session(
    session: ConsultationSession,
    text: str,
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    category = session.complaint_category
    answers = dict(session.answers)
    asked = set(session.asked_question_ids)

    if session.current_question_id:
        question = get_question_by_id(category, session.current_question_id)
        if question is not None:
            answers[question.id] = text
            _persist_answer_to_emr(
                session.patient_id,
                session.visit_id,
                question.id,
                text,
            )

            if question.red_flag_patterns and check_answer_red_flag(
                text, question.red_flag_patterns
            ):
                flags = detect_consultation_red_flags(text)
                if question.red_flag_label and question.red_flag_label not in flags:
                    flags.append(question.red_flag_label)
                visit_id = session.visit_id
                _persist_emergency(session.patient_id, visit_id, text, flags)
                update_session(
                    session.id,
                    phase="emergency",
                    answers=answers,
                    clear_current_question=True,
                )
                if user_data is not None:
                    user_data.pop(CONSULTATION_SESSION_KEY, None)
                detail = question.red_flag_label or "xavfli belgilar"
                return ConsultationTurnResult(
                    reply=build_consultation_emergency_response(flags, detail=detail),
                    phase="emergency",
                    session_id=session.id,
                    emergency=True,
                    used_consultation_engine=True,
                )

    asked.add(session.current_question_id or "")

    if has_enough_information(category, asked - {""}, answers):
        return _complete_session(session, answers, user_data=user_data)

    next_question = select_next_question(category, asked - {""}, answers)
    if next_question is None:
        return _complete_session(session, answers, user_data=user_data)

    new_asked = list(asked - {""})
    if next_question.id not in new_asked:
        new_asked.append(next_question.id)

    update_session(
        session.id,
        asked_question_ids=new_asked,
        answers=answers,
        current_question_id=next_question.id,
    )
    if user_data is not None:
        user_data[CONSULTATION_SESSION_KEY] = session.id

    return ConsultationTurnResult(
        reply=next_question.text,
        phase="collecting",
        session_id=session.id,
        used_consultation_engine=True,
    )


def _complete_session(
    session: ConsultationSession,
    answers: dict[str, str],
    *,
    user_data: dict[str, Any] | None,
) -> ConsultationTurnResult:
    flags = detect_consultation_red_flags(" ".join(answers.values()))
    summary = generate_consultation_summary(
        session.complaint_category,
        answers,
        red_flags=flags,
    )
    summary_dict = summary.to_dict()
    summary_text = summary.format_text()

    _persist_summary_to_emr(session.patient_id, session.visit_id, summary, answers)
    update_session(
        session.id,
        phase="complete",
        answers=answers,
        clear_current_question=True,
        summary=summary_dict,
    )
    if user_data is not None:
        user_data.pop(CONSULTATION_SESSION_KEY, None)

    offers = _build_completion_offers(session.patient_id, summary.urgency)
    reply = f"{summary_text}\n\n{offers}"

    logger.info(
        "consultation_completed patient_id=%s session_id=%s urgency=%s",
        session.patient_id,
        session.id,
        summary.urgency,
    )
    return ConsultationTurnResult(
        reply=reply,
        phase="complete",
        session_id=session.id,
        used_consultation_engine=True,
        completed=True,
    )


def _persist_answer_to_emr(
    patient_id: int,
    visit_id: int,
    question_id: str,
    answer: str,
) -> None:
    visit = get_emr_visit(visit_id)
    if visit is None:
        return
    block = f"Q[{question_id}]: {answer.strip()}"
    existing = visit.get("notes") or ""
    if block in existing:
        return
    merged = f"{existing}\n{block}".strip() if existing else block
    edit_visit(patient_id, visit_id, notes=merged)


def _persist_summary_to_emr(
    patient_id: int,
    visit_id: int,
    summary: Any,
    answers: dict[str, str],
) -> None:
    qa_block = "\n".join(
        f"Q[{key}]: {value}" for key, value in sorted(answers.items()) if value.strip()
    )
    notes = f"{qa_block}\n\n--- Konsultatsiya xulosasi ---\n{summary.format_text()}"
    edit_visit(
        patient_id,
        visit_id,
        main_complaint=summary.chief_complaint,
        recommended_examinations="; ".join(summary.recommended_investigations),
        follow_up_schedule=summary.follow_up_plan,
        notes=notes,
        preliminary_diagnosis="; ".join(summary.possible_differential_diagnoses[:3]),
    )


def _persist_emergency(
    patient_id: int,
    visit_id: int,
    text: str,
    flags: list[str],
) -> None:
    note = (
        f"SHOSHILINCH: {', '.join(flags)}\n"
        f"Bemor xabari: {text.strip()}\n"
        f"Sana: {clinic_today_iso()}"
    )
    visit = get_emr_visit(visit_id)
    existing = (visit or {}).get("notes") or ""
    merged = f"{existing}\n{note}".strip() if existing else note
    edit_visit(patient_id, visit_id, notes=merged)


def _build_completion_offers(patient_id: int, urgency: str) -> str:
    lines = [
        "✅ **Konsultatsiya yakunlandi. Keyingi qadamlar:**",
        "",
        "1️⃣ **Onlayn konsultatsiya** — \"onlayn yozilish\" deb yozing",
        "2️⃣ **Klinikada qabul** — \"qabulga yozilish\" deb yozing",
    ]

    recommendation = recommend_clinic_for_patient(patient_id, specialty="nevrolog")
    if recommendation:
        distance = recommendation.get("distance_km")
        distance_text = f" ({distance} km)" if distance is not None else ""
        lines.extend(
            [
                "",
                f"3️⃣ **Eng yaqin klinika:** {recommendation['clinic_name']}{distance_text}",
                f"   Manzil: {recommendation['address']}",
            ]
        )
        if recommendation.get("google_maps_link"):
            lines.append(f"   Xarita: {recommendation['google_maps_link']}")
        times = recommendation.get("available_appointment_times") or []
        if times:
            preview = ", ".join(times[:3])
            lines.append(f"   Mavjud vaqtlar (bugun): {preview}")
        lines.append(
            f"4️⃣ **Mavjud shifokor:** {recommendation['staff_name']} "
            f"({recommendation.get('specialty') or 'nevrolog'})"
        )
    else:
        lines.extend(
            [
                "",
                "3️⃣ **Eng yaqin klinika** — lokatsiyangizni ulashganingizdan keyin tavsiya beraman.",
                "4️⃣ **Mavjud shifokor** — qabulga yozilish orqali tanlang.",
            ]
        )

    if urgency == "urgent":
        lines.append("\n⚠️ Holatingiz tezroq shaxsiy ko'rikni talab qilishi mumkin.")
    return "\n".join(lines)
