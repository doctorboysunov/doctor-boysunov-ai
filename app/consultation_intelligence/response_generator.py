"""Response generation — templates only; no clinical decisions."""

from __future__ import annotations

from app.clinical_brain.senior_neurologist import (
    ConsultationClosureSummary,
    build_closure_summary,
    format_patient_closure_summary,
)
from app.clinical_brain.types import ClinicalBrainInternal, DoctorEmrUpdate, RankedHypothesis
from app.consultation_intelligence.decision_engine import ClinicalDecision
from app.consultation_intelligence.patient_labels import format_fact_for_patient
from app.consultation_intelligence.state import ConsultationState


_ACK = (
    "Tushundim.",
    "Rahmat, aytdiklaringizni inobatga oldim.",
    "Ma'lumot uchun rahmat.",
)


def _ack(turn: int) -> str:
    return _ACK[turn % len(_ACK)]


class ResponseGenerator:
    """Turn structured decisions into patient-facing Uzbek text."""

    def greeting_resume(self, pending_question: str | None) -> str:
        if pending_question:
            return f"Assalomu alaykum. Davom etamiz — iltimos, oxirgi savolimga javob bering: {pending_question}"
        return "Assalomu alaykum. Konsultatsiyamiz davom etmoqda — holatingizni davom ettiring."

    def topic_clarification(self) -> str:
        return (
            "Yangi muammo haqida gapiryapsizmi? "
            "Agar shunday bo'lsa, aniq yozing: «yangi muammo». "
            "Aks holda joriy konsultatsiyani davom ettiramiz."
        )

    def advice_during_consultation(self, state: ConsultationState, pending_question: str | None) -> str:
        intro = (
            "Hozircha aniq davolash rejasini aytolmayman — avval muhim savollarga javob olishim kerak. "
            "To'liq ma'lumotdan keyin shifokor aniq yo'l ko'rsatadi."
        )
        if pending_question:
            q = pending_question.rstrip("?")
            return f"{intro}\n\nDavom etamiz: {q}?"
        if state.missing_information:
            return f"{intro}\n\nAgar qo'shimcha belgi bo'lsa, yozing — konsultatsiyani davom ettiramiz."
        return intro

    def continue_after_help_action(self, state: ConsultationState) -> str:
        return (
            "Konsultatsiyamiz davom etmoqda — oldingi ma'lumotlaringiz saqlangan. "
            "Agar qo'shimcha savol yoki yangi belgi bo'lsa, yozing. "
            "Shifokor ko'rigida aniq reja tuziladi."
        )

    def first_question(self, state: ConsultationState, decision: ClinicalDecision) -> str:
        return (
            f"Sizning asosiy muammoingiz {state.syndrome_label_uz} bilan bog'liq ko'rinadi. "
            f"Bir necha muhim savol beraman. {decision.question_text.rstrip('?')}?"
        )

    def follow_up_question(self, state: ConsultationState, decision: ClinicalDecision, user_message: str) -> str:
        echo = " ".join(user_message.strip().split()[:6])
        prefix = f"{_ack(state.turn_count)}"
        if echo:
            prefix = f"{prefix} ({echo}…)"
        q = decision.question_text.rstrip("?")
        return f"{prefix} {q}?"

    def closure(self, state: ConsultationState) -> str:
        hypotheses = [
            RankedHypothesis(
                name=d["name"],
                probability="high" if d.get("rank") == 1 else "medium",
                probability_pct=float(d.get("probability_pct") or 0),
            )
            for d in state.differential[:5]
        ]
        internal = ClinicalBrainInternal(
            step1_patient_meaning=state.opening_complaint or state.dominant_complaint,
            step3_hypotheses=hypotheses,
            step4_emergency_assessment="urgent" if state.confirmed_red_flags else "routine",
        )
        closure = build_closure_summary(
            internal=internal,
            doctor_emr=DoctorEmrUpdate(),
            dominant=None,
        )
        closure.chief_complaint = state.dominant_complaint
        closure.neurological_syndrome = state.syndrome_label_uz
        fact_lines = [
            format_fact_for_patient(state, fact)
            for fact in state.facts
            if fact.topic_slug != "opening_complaint"
        ]
        fact_lines = [line for line in fact_lines if line]
        parts = [f"Asosiy shikoyat: {state.dominant_complaint}. Faol sindrom: {state.syndrome_label_uz}."]
        parts.extend(fact_lines[:5])
        closure.clinical_summary = " ".join(parts[:6])
        if state.differential:
            closure.most_likely_diagnosis = state.differential[0]["name"]
            closure.differential_diagnosis = [d["name"] for d in state.differential[1:4]]
        return format_patient_closure_summary(closure)

    def emergency(self, flags: list[str]) -> str:
        from app.services.consultation_red_flags import build_consultation_emergency_response

        return build_consultation_emergency_response(flags or ["confirmed_clinical_emergency"])

    def to_closure_summary(self, state: ConsultationState) -> dict:
        text = self.closure(state)
        return {
            "consultation_closure": {
                "clinical_summary": state.opening_complaint,
                "neurological_syndrome": state.syndrome_label_uz,
                "most_likely_diagnosis": state.differential[0]["name"] if state.differential else "",
                "differential_diagnosis": [d["name"] for d in state.differential[1:4]],
            },
            "clinical_pathway_id": state.pathway_id,
            "neurological_syndrome": state.syndrome_label_uz,
            "engine_version": state.to_dict().get("engine_version"),
        }
