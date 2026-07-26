"""AI Medical Assistant — GPT reasoning engine (Phase 12 Universal Medical Brain)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.clinical_brain.types import DoctorEmrUpdate
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.domain.consultation import ComplaintCategory
from app.domain.medical import MedicalSpecialty
from app.consultation_intelligence import process_consultation_intelligence_turn
from app.medical_brain.engine import build_medical_brain_input, medical_brain_to_legacy_summary, run_medical_brain
from app.safety.safety_layer import enforce_safety
from app.services.consultation_classifier import complaint_label
from openai import OpenAI

logger = logging.getLogger("doctor_boysunov.consultation_ai")
client = OpenAI(api_key=OPENAI_API_KEY)

LEGAL_DISCLAIMER = (
    "⚠️ Bu maslahat ta'limiy xarakterda. Aniq tashxis va davolash uchun shifokor ko'rigi kerak."
)

HELP_MENU_QUESTION = "Keyingi qadamda sizga qanday yordam beray?"

HELP_MENU_OPTIONS = (
    "• Savollarni davom ettirish\n"
    "• Onlayn konsultatsiya\n"
    "• Klinikada qabul"
)

HELP_MENU_TEXT = f"{HELP_MENU_QUESTION}\n{HELP_MENU_OPTIONS}"

UNDERSTOOD_PREFIX = "Men sizning holatingizni tushundim."

GREETING_RESUME_PROMPT = (
    "Assalomu alaykum. Davom etayotgan konsultatsiyamiz bor. "
    "Uni davom ettiramizmi yoki yangi muammo bo'yicha boshlaymiz?"
)

COMPLAINT_SWITCH_PROMPT = (
    "Siz yangi shikoyat haqida gapiryapsizmi yoki oldingi shikoyatni davom ettiryapsizmi?"
)

ConversationAction = Literal[
    "continue_session",
    "ask_session_choice",
    "ask_complaint_clarification",
    "start_new_session",
]


@dataclass
class InternalReasoning:
    what_i_know: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    emergency_assessment: str = "none"
    possible_neurological_causes: list[str] = field(default_factory=list)
    next_question_topic: str = ""
    next_question_rationale: str = ""

    @classmethod
    def from_clinical_brain(cls, internal: Any) -> InternalReasoning:
        return cls(
            what_i_know=internal.what_i_know,
            missing_information=internal.step5_missing_information,
            emergency_assessment=internal.step4_emergency_assessment,
            possible_neurological_causes=internal.possible_neurological_causes,
            next_question_topic=internal.step6_next_question_topic,
            next_question_rationale=internal.step6_next_question_rationale,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> InternalReasoning:
        if not data:
            return cls()
        return cls(
            what_i_know=[str(x) for x in (data.get("what_i_know") or []) if str(x).strip()],
            missing_information=[str(x) for x in (data.get("missing_information") or []) if str(x).strip()],
            emergency_assessment=str(data.get("emergency_assessment") or "none"),
            possible_neurological_causes=[
                str(x) for x in (data.get("possible_neurological_causes") or []) if str(x).strip()
            ],
            next_question_topic=str(data.get("next_question_topic") or ""),
            next_question_rationale=str(data.get("next_question_rationale") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "what_i_know": self.what_i_know,
            "missing_information": self.missing_information,
            "emergency_assessment": self.emergency_assessment,
            "possible_neurological_causes": self.possible_neurological_causes,
            "next_question_topic": self.next_question_topic,
            "next_question_rationale": self.next_question_rationale,
        }

    def format_emr_reasoning(self) -> str:
        lines = ["--- AI klinik mulohaza (shifokor uchun) ---"]
        if self.what_i_know:
            lines.append(f"Ma'lum: {'; '.join(self.what_i_know)}")
        if self.missing_information:
            lines.append(f"Yetishmaydi: {'; '.join(self.missing_information)}")
        if self.possible_neurological_causes:
            lines.append(f"Ehtimoliy sabablar: {'; '.join(self.possible_neurological_causes)}")
        if self.next_question_rationale:
            lines.append(f"Keyingi savol asosi: {self.next_question_rationale}")
        lines.append(f"Favqulodda baho: {self.emergency_assessment}")
        return "\n".join(lines)


@dataclass
class NeurologyTurnOutput:
    patient_reply: str = ""
    ready_for_help_menu: bool = False
    brief_summary_for_patient: str = ""
    known_facts: dict[str, Any] = field(default_factory=dict)
    topics_covered: list[str] = field(default_factory=list)
    doctor_emr: DoctorEmrUpdate = field(default_factory=DoctorEmrUpdate)
    internal_reasoning: InternalReasoning = field(default_factory=InternalReasoning)
    session_summary: dict[str, Any] = field(default_factory=dict)
    append_disclaimer: bool = False
    primary_specialty: MedicalSpecialty = "internal_medicine"
    secondary_specialties: list[MedicalSpecialty] = field(default_factory=list)

    @property
    def suggests_emergency(self) -> bool:
        assessment = (self.internal_reasoning.emergency_assessment or "").lower()
        return assessment in {"emergency", "urgent", "shoshilinch", "103"}


@dataclass
class ConversationIntentAnalysis:
    is_greeting: bool = False
    is_answering_previous_question: bool = False
    is_new_complaint: bool = False
    is_topic_change: bool = False
    wants_restart: bool = False
    detected_complaint_category: str = ""
    confidence: str = "low"
    recommended_action: ConversationAction = "ask_complaint_clarification"
    reasoning: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConversationIntentAnalysis:
        if not data:
            return cls()
        action = str(data.get("recommended_action") or "ask_complaint_clarification")
        valid_actions = {
            "continue_session",
            "ask_session_choice",
            "ask_complaint_clarification",
            "start_new_session",
        }
        if action not in valid_actions:
            action = "ask_complaint_clarification"
        return cls(
            is_greeting=bool(data.get("is_greeting")),
            is_answering_previous_question=bool(data.get("is_answering_previous_question")),
            is_new_complaint=bool(data.get("is_new_complaint")),
            is_topic_change=bool(data.get("is_topic_change")),
            wants_restart=bool(data.get("wants_restart")),
            detected_complaint_category=str(data.get("detected_complaint_category") or ""),
            confidence=str(data.get("confidence") or "low"),
            recommended_action=action,  # type: ignore[arg-type]
            reasoning=str(data.get("reasoning") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_greeting": self.is_greeting,
            "is_answering_previous_question": self.is_answering_previous_question,
            "is_new_complaint": self.is_new_complaint,
            "is_topic_change": self.is_topic_change,
            "wants_restart": self.wants_restart,
            "detected_complaint_category": self.detected_complaint_category,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
            "reasoning": self.reasoning,
        }

    @property
    def should_continue(self) -> bool:
        return (
            self.recommended_action == "continue_session"
            and self.confidence in {"high", "medium"}
            and (self.is_answering_previous_question or not self.is_topic_change)
        )


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _limit_sentences(text: str, max_sentences: int = 4) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) <= max_sentences:
        return cleaned
    return " ".join(parts[:max_sentences]).strip()


def run_intelligence_turn(
    *,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
    topics_covered: list[str],
    prior_complaints: list[str],
    patient_id: int = 0,
    visit_history: dict[str, Any] | None = None,
    append_disclaimer: bool = False,
    category: ComplaintCategory | None = None,
    primary_specialty: str | None = None,
    secondary_specialties: list[str] | None = None,
) -> NeurologyTurnOutput:
    """Code-driven consultation — ConsultationState + ClinicalReasoner + DecisionEngine (v6)."""
    answers = dict(known_facts or {})
    if topics_covered:
        answers["topics_covered"] = list(topics_covered)

    result = process_consultation_intelligence_turn(
        user_message=user_message,
        session_messages=session_messages,
        answers=answers,
    )
    state = result.consultation_state

    if result.suggests_emergency:
        return NeurologyTurnOutput(
            patient_reply=result.patient_reply,
            internal_reasoning=InternalReasoning(emergency_assessment="emergency"),
            session_summary={"emergency_flags": result.emergency_flags},
            known_facts=answers,
            topics_covered=list(state.answered_slugs),
        )

    reply = result.patient_reply
    if append_disclaimer:
        reply, _ = append_legal_disclaimer(reply, already_appended=False)

    fact_values = [f.parsed_value or f.raw_answer for f in state.facts]
    return NeurologyTurnOutput(
        patient_reply=reply,
        ready_for_help_menu=result.ready_for_help_menu,
        brief_summary_for_patient=result.brief_summary_for_patient,
        known_facts=answers,
        topics_covered=list(state.answered_slugs),
        doctor_emr=DoctorEmrUpdate.from_dict(result.doctor_emr),
        internal_reasoning=InternalReasoning(
            what_i_know=fact_values,
            missing_information=list(state.missing_information),
            emergency_assessment="none",
            possible_neurological_causes=[state.syndrome_label_uz or state.pathway_id],
            next_question_topic=state.pending_topic or "",
            next_question_rationale=state.recognition_rationale,
        ),
        session_summary=result.session_summary,
        append_disclaimer=append_disclaimer,
        primary_specialty="neurology",
        secondary_specialties=[],
    )


def run_medical_turn(
    *,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
    topics_covered: list[str],
    prior_complaints: list[str],
    patient_id: int = 0,
    visit_history: dict[str, Any] | None = None,
    append_disclaimer: bool = False,
    primary_specialty: str | None = None,
    secondary_specialties: list[str] | None = None,
    category: ComplaintCategory | None = None,
) -> NeurologyTurnOutput:
    """Universal Medical Brain turn — coordinates all specialties."""
    brain_input = build_medical_brain_input(
        patient_id=patient_id,
        user_message=user_message,
        session_messages=session_messages,
        known_facts=known_facts,
        topics_covered=topics_covered,
        prior_complaints=prior_complaints,
        visit_history=visit_history,
        primary_specialty=primary_specialty,
        secondary_specialties=secondary_specialties,
    )
    if category:
        brain_input.complaint_category = category

    brain_output = run_medical_brain(brain_input)
    legacy = medical_brain_to_legacy_summary(brain_output)
    internal = brain_output.internal
    return NeurologyTurnOutput(
        patient_reply=brain_output.patient_reply,
        ready_for_help_menu=brain_output.ready_for_help_menu,
        brief_summary_for_patient=brain_output.brief_summary_for_patient,
        known_facts=brain_output.known_facts,
        topics_covered=brain_output.topics_covered,
        doctor_emr=brain_output.doctor_emr,
        internal_reasoning=InternalReasoning(
            what_i_know=internal.what_i_know,
            missing_information=internal.step5_missing_information,
            emergency_assessment=internal.step4_emergency_assessment,
            possible_neurological_causes=internal.possible_causes,
            next_question_topic=internal.step6_next_question_topic,
            next_question_rationale=internal.step6_next_question_rationale,
        ),
        session_summary=legacy,
        append_disclaimer=append_disclaimer,
        primary_specialty=brain_output.primary_specialty,
        secondary_specialties=brain_output.secondary_specialties,
    )


def run_neurology_turn(
    *,
    category: ComplaintCategory,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
    topics_covered: list[str],
    prior_complaints: list[str],
    patient_id: int = 0,
    visit_history: dict[str, Any] | None = None,
    append_disclaimer: bool = False,
) -> NeurologyTurnOutput:
    """Backward-compatible wrapper — delegates to Universal Medical Brain."""
    return run_medical_turn(
        category=category,
        user_message=user_message,
        session_messages=session_messages,
        known_facts=known_facts,
        topics_covered=topics_covered,
        prior_complaints=prior_complaints,
        patient_id=patient_id,
        visit_history=visit_history,
        append_disclaimer=append_disclaimer,
        primary_specialty="neurology",
    )


def run_help_followup_turn(
    *,
    category: ComplaintCategory,
    choice: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
) -> str:
    """GPT-generated short reply after patient selects help option."""
    choice_labels = {
        "online": "Onlayn konsultatsiya tanladi",
        "clinic": "Klinikada qabul tanladi",
        "continue": "Savollarni davom ettirishni tanladi",
    }
    prompt = (
        f"Bemor {choice_labels.get(choice, choice)}. "
        f"Shikoyat turi: {complaint_label(category)}. "
        "2-3 qisqa o'zbekcha gap bilan javob bering. Do'stona, tabiiy. "
        "Aniq retsept yoki tashxis bermang."
    )
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        instructions="Return plain text only, 2-3 short sentences in Uzbek.",
    )
    raw = response.output_text or ""
    safe, _ = enforce_safety(user_message=choice, ai_response=raw)
    return _limit_sentences(safe, 3)


def build_help_menu_reply(brief_summary: str) -> str:
    summary = _limit_sentences(brief_summary or "Asosiy belgilaringizni inobatga oldim.", 2)
    intro = f"{UNDERSTOOD_PREFIX}\n\n{summary}\n\n{HELP_MENU_TEXT}"
    return intro


def parse_help_choice(text: str) -> str | None:
    normalized = text.strip().lower()
    if any(word in normalized for word in ("davom", "savol", "continue", "yana", "savollar")):
        return "continue"
    if any(word in normalized for word in ("onlayn", "online", "video")):
        return "online"
    if any(word in normalized for word in ("qabul", "klinik", "clinic", "offline", "oflayn")):
        return "clinic"
    return None


def append_legal_disclaimer(reply: str, *, already_appended: bool) -> tuple[str, bool]:
    if already_appended or LEGAL_DISCLAIMER in reply:
        return reply, True
    main = _limit_sentences(reply, 4)
    return f"{main}\n\n{LEGAL_DISCLAIMER}", True


def _last_assistant_message(session_messages: list[dict[str, str]]) -> str:
    for item in reversed(session_messages):
        if item.get("role") == "assistant":
            return str(item.get("content") or "")
    return ""


def _build_conversation_intent_instructions(
    *,
    current_category: ComplaintCategory,
    session_phase: str,
    known_facts: dict[str, Any],
    last_assistant_message: str,
    conversation_history: str,
) -> str:
    return f"""You analyze patient messages during an active neurology consultation on Telegram.
The AI owns conversation flow — never assume the patient is continuing the previous topic unless confident.

Current consultation complaint: {complaint_label(current_category)}
Session phase: {session_phase}
Known facts: {json.dumps(known_facts, ensure_ascii=False)}
Last assistant message (the question/context patient may be answering):
{last_assistant_message or "none"}

Recent conversation:
{conversation_history}

For the patient's latest message, determine:
1) Is this only a greeting (Salom, Assalomu alaykum, Hello, etc.)?
2) Is the patient clearly answering the previous question?
3) Has a new complaint started or the topic changed (e.g. headache → neck pain → back pain)?
4) Does the patient want to restart or switch to a new problem?
5) How confident are you?

Return ONLY valid JSON:
{{
  "is_greeting": false,
  "is_answering_previous_question": false,
  "is_new_complaint": false,
  "is_topic_change": false,
  "wants_restart": false,
  "detected_complaint_category": "headache|neck_pain|low_back_pain|other_neurological|...",
  "confidence": "high|medium|low",
  "recommended_action": "continue_session|ask_session_choice|ask_complaint_clarification|start_new_session",
  "reasoning": "brief explanation"
}}

Action rules:
- Pure greeting during active consultation → ask_session_choice
- Clear answer to last assistant question, same complaint → continue_session (confidence high/medium)
- Different body part/complaint than current session → ask_complaint_clarification (unless wants_restart with high confidence → start_new_session)
- Explicit restart/new problem request → start_new_session
- Low confidence or ambiguous → ask_complaint_clarification (NOT continue_session)
- Never recommend continue_session unless confident patient answers the previous question."""


def run_conversation_intent_analysis(
    *,
    current_category: ComplaintCategory,
    session_phase: str,
    user_message: str,
    session_messages: list[dict[str, str]],
    known_facts: dict[str, Any],
) -> ConversationIntentAnalysis:
    snippet_lines = [
        f"{item['role']}: {item['content'][:400]}"
        for item in session_messages[-12:]
    ]
    conversation_history = "\n".join(snippet_lines) or f"user: {user_message}"
    instructions = _build_conversation_intent_instructions(
        current_category=current_category,
        session_phase=session_phase,
        known_facts=known_facts,
        last_assistant_message=_last_assistant_message(session_messages),
        conversation_history=conversation_history,
    )
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=user_message,
        instructions=instructions,
    )
    raw = response.output_text or ""
    logger.info("conversation_intent_analysis category=%s raw_len=%s", current_category, len(raw))
    data = _extract_json(raw)
    analysis = ConversationIntentAnalysis.from_dict(data)
    return _normalize_intent_analysis(analysis, user_message, current_category)


def _normalize_intent_analysis(
    analysis: ConversationIntentAnalysis,
    user_message: str,
    current_category: ComplaintCategory,
) -> ConversationIntentAnalysis:
    normalized = user_message.strip().lower()
    greeting_only = normalized in {
        "salom",
        "assalomu alaykum",
        "assalom",
        "hello",
        "hi",
        "hayrli kun",
        "hayrli tong",
    } or (
        len(normalized.split()) <= 3
        and any(word in normalized for word in ("salom", "assalom", "hello", "hi"))
        and not any(hint in normalized for hint in ("og'ri", "ogri", "shikoyat", "kasal", "og‘ri"))
    )
    if greeting_only:
        analysis.is_greeting = True
        analysis.recommended_action = "ask_session_choice"
        analysis.confidence = "high"
        return analysis

    from app.services.consultation_classifier import classify_complaint

    detected = analysis.detected_complaint_category or classify_complaint(user_message)
    if detected and detected != current_category and is_medical_complaint(user_message):
        analysis.is_topic_change = True
        analysis.is_new_complaint = True
        if analysis.recommended_action == "continue_session" and analysis.confidence != "high":
            analysis.recommended_action = "ask_complaint_clarification"

    if analysis.recommended_action == "continue_session" and analysis.confidence == "low":
        analysis.recommended_action = "ask_complaint_clarification"

    return analysis


def parse_session_choice(text: str) -> str | None:
    normalized = text.strip().lower()
    if any(word in normalized for word in ("yangi", "boshqa", "restart", "boshqadan", "yangi muammo")):
        return "new"
    if any(word in normalized for word in ("davom", "oldingi", "ha", "shu", "continue", "konsultatsiya")):
        return "continue"
    return None


def parse_complaint_clarification(text: str) -> str | None:
    normalized = text.strip().lower()
    if any(word in normalized for word in ("yangi", "boshqa shikoyat", "boshqa muammo", "ha yangi")):
        return "new_complaint"
    if any(word in normalized for word in ("oldingi", "davom", "shu shikoyat", "oldingi shikoyat", "ha oldingi")):
        return "continue_previous"
    return None


def is_medical_complaint(message: str) -> bool:
    from app.services.location_profile import is_medical_complaint as _is_medical

    return _is_medical(message)

