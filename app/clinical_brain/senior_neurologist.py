"""Phase 3 вЂ” Senior Neurologist Clinical Intelligence.

Reason like a senior neurologist; communicate in simple Uzbek for patients.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.clinical_brain.types import ClinicalBrainInternal, DoctorEmrUpdate, RankedHypothesis
from app.domain.consultation import ComplaintCategory
from app.services.consultation_classifier import complaint_label

PHASE_3_VERSION = "3.1.0"

# Keyword clusters for multi-complaint detection (Uzbek + common variants)
_COMPLAINT_SIGNALS: dict[ComplaintCategory, tuple[str, ...]] = {
    "headache": ("bosh og", "boshim og", "bosh og'ri", "bosh ogвЂri", "migren", "bosh a", "cephalgia"),
    "neck_pain": ("bo'yin og", "boyin og", "boвЂyin og", "boynim og", "servikal", "miyoq"),
    "low_back_pain": ("bel og", "belim og", "belim ham og", "bel og'ri", "bel ogвЂri", "orqa og", "lumb", "kamar og"),
    "vertigo": ("aylan", "bosh aylan", "vertigo", "vertig"),
    "stroke": ("insult", "falaj", "nutq buz", "qo'lim ishlam", "qoвЂlim ishlam", "yuz qimir"),
    "neuropathy": ("uyuq", "qiynish", "karaxt", "neuropat", "sezgi"),
    "facial_nerve_palsy": ("yuz falaj", "yuz qimir", "bell", "yuzning bir"),
    "tremor": ("titro", "tremor", "qaltir"),
    "memory_problems": ("xotira", "eslay olmay", "unut", "demens"),
    "sleep_disorders": ("uxlamay", "uyqu", "uxlab qol", "insomnia"),
    "anxiety": ("xavotir", "tashvish", "panik", "asabiylash"),
    "depression": ("depress", "kayfiyat", "havas yo'q", "havas yoвЂq"),
}


@dataclass(frozen=True)
class ComplaintCluster:
    category: ComplaintCategory
    label_uz: str
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class DominantComplaintAnalysis:
    dominant_category: ComplaintCategory
    dominant_label: str
    secondary_complaints: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ConsultationClosureSummary:
    chief_complaint: str = ""
    clinical_summary: str = ""
    associated_symptoms: list[str] = field(default_factory=list)
    neurological_syndrome: str = ""
    most_likely_diagnosis: str = ""
    differential_diagnosis: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    recommended_investigations: list[str] = field(default_factory=list)
    treatment_strategy: str = ""
    recommended_next_step: str = ""
    urgent_referral_required: bool = False
    urgent_referral_reason: str = ""
    # Backward-compatible alias used in earlier Phase 3 payloads
    ranked_diagnoses: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ranked_diagnoses and not self.differential_diagnosis:
            self.differential_diagnosis = list(self.ranked_diagnoses)
        elif self.differential_diagnosis and not self.ranked_diagnoses:
            self.ranked_diagnoses = list(self.differential_diagnosis)

    def to_dict(self) -> dict[str, Any]:
        dx = self.differential_diagnosis or self.ranked_diagnoses
        return {
            "chief_complaint": self.chief_complaint,
            "clinical_summary": self.clinical_summary,
            "associated_symptoms": self.associated_symptoms,
            "neurological_syndrome": self.neurological_syndrome,
            "most_likely_diagnosis": self.most_likely_diagnosis,
            "differential_diagnosis": dx,
            "ranked_diagnoses": dx,
            "red_flags": self.red_flags,
            "recommended_investigations": self.recommended_investigations,
            "treatment_strategy": self.treatment_strategy,
            "recommended_next_step": self.recommended_next_step,
            "next_step": self.recommended_next_step,
            "urgent_referral_required": self.urgent_referral_required,
            "urgent_referral_reason": self.urgent_referral_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ConsultationClosureSummary:
        if not data:
            return cls()

        def _str_list(key: str, alt: str = "") -> list[str]:
            raw = data.get(key) or (data.get(alt) if alt else None) or []
            if isinstance(raw, str):
                return [raw.strip()] if raw.strip() else []
            return [str(x) for x in raw if str(x).strip()]

        dx = _str_list("differential_diagnosis", "ranked_diagnoses") or _str_list("possible_diagnoses")
        associated = _str_list("associated_symptoms")
        investigations = _str_list("recommended_investigations")

        return cls(
            chief_complaint=str(data.get("chief_complaint") or ""),
            clinical_summary=str(data.get("clinical_summary") or ""),
            associated_symptoms=associated,
            neurological_syndrome=str(data.get("neurological_syndrome") or ""),
            most_likely_diagnosis=str(data.get("most_likely_diagnosis") or ""),
            differential_diagnosis=dx,
            ranked_diagnoses=dx,
            red_flags=_str_list("red_flags", "red_flags_noted"),
            recommended_investigations=investigations,
            treatment_strategy=str(data.get("treatment_strategy") or ""),
            recommended_next_step=str(data.get("recommended_next_step") or data.get("next_step") or ""),
            urgent_referral_required=bool(data.get("urgent_referral_required") or data.get("urgent_referral")),
            urgent_referral_reason=str(data.get("urgent_referral_reason") or ""),
        )


def _normalize(text: str) -> str:
    return text.lower().replace("'", "'").replace("'", "'").replace("вЂ", "'").replace("вЂ™", "'")


def detect_complaint_clusters(message: str) -> list[ComplaintCluster]:
    """Detect distinct complaint themes in one patient message."""
    lowered = _normalize(message)
    found: list[ComplaintCluster] = []
    for category, terms in _COMPLAINT_SIGNALS.items():
        hits = tuple(t for t in terms if t in lowered)
        if hits:
            found.append(
                ComplaintCluster(
                    category=category,
                    label_uz=complaint_label(category),
                    matched_terms=hits,
                )
            )
    # Uzbek morphology: "belim ham og'riyapti" вЂ” bel and og'ri separated by ham/other words
    if not any(c.category == "low_back_pain" for c in found):
        if re.search(r"bel\w*\s+(?:ham\s+)?og[''']?ri", lowered):
            found.append(
                ComplaintCluster(
                    category="low_back_pain",
                    label_uz=complaint_label("low_back_pain"),
                    matched_terms=("belвЂ¦og'ri",),
                )
            )
    # Uzbek morphology: "boshim ham og'riyapti" — bosh and og'ri separated by ham/other words
    if not any(c.category == "headache" for c in found):
        if re.search(r"bosh\w*\s+(?:ham\s+)?og[''']?ri", lowered):
            found.append(
                ComplaintCluster(
                    category="headache",
                    label_uz=complaint_label("headache"),
                    matched_terms=("bosh…og'ri",),
                )
            )
    return found


def _severity_score(category: ComplaintCategory, terms: tuple[str, ...], text: str) -> int:
    score = len(terms) * 10
    emergency_boost = {
        "stroke": 100,
        "headache": 40 if any(w in text for w in ("birdan", "eng kuchli", "thunderclap", "hush")) else 0,
        "low_back_pain": 35 if any(w in text for w in ("hojatxona", "siydik", "oyoq kuchsiz")) else 0,
        "vertigo": 30 if any(w in text for w in ("doimiy", "nutq", "ko'rish")) else 0,
    }
    score += emergency_boost.get(category, 0)
    if category in {"stroke", "headache", "low_back_pain", "vertigo"}:
        score += 5
    return score


def identify_dominant_complaint(
    message: str,
    category_hint: ComplaintCategory | str = "other_neurological",
) -> DominantComplaintAnalysis:
    """Pick the dominant complaint when multiple are present; explain why."""
    clusters = detect_complaint_clusters(message)
    hint: ComplaintCategory = category_hint if category_hint in _COMPLAINT_SIGNALS else "other_neurological"  # type: ignore[assignment]

    if not clusters:
        return DominantComplaintAnalysis(
            dominant_category=hint,
            dominant_label=complaint_label(hint),
            secondary_complaints=[],
            rationale="Bitta asosiy shikoyat вЂ” bemorning hikoyasiga e'tibor qaratiladi.",
        )

    if len(clusters) == 1:
        c = clusters[0]
        return DominantComplaintAnalysis(
            dominant_category=c.category,
            dominant_label=c.label_uz,
            secondary_complaints=[],
            rationale="Bitta aniq shikoyat aniqlandi вЂ” konsultatsiya shu muammoga markazlanadi.",
        )

    lowered = _normalize(message)
    ranked = sorted(
        clusters,
        key=lambda c: _severity_score(c.category, c.matched_terms, lowered),
        reverse=True,
    )
    dominant = ranked[0]
    secondary = [c.label_uz for c in ranked[1:]]

    rationale_parts = [
        f"Asosiy e'tibor '{dominant.label_uz}' ga вЂ” xavfsizlik va klinik ahamiyat bo'yicha ustun.",
    ]
    if dominant.category == "stroke":
        rationale_parts.append("O'tkir nevrologik belgilar yoki insult shubhasi вЂ” darhol ajratiladi.")
    elif dominant.category == "headache" and any(w in lowered for w in ("birdan", "eng kuchli")):
        rationale_parts.append("Birdan boshlangan kuchli bosh og'rig'i вЂ” xavfli sabablarni istisno qilish kerak.")
    if secondary:
        rationale_parts.append(f"Qo'shimcha shikoyatlar keyinroq baholanadi: {', '.join(secondary)}.")

    return DominantComplaintAnalysis(
        dominant_category=dominant.category,
        dominant_label=dominant.label_uz,
        secondary_complaints=secondary,
        rationale=" ".join(rationale_parts),
    )


def format_communication_style_block() -> str:
    """Patient-facing communication rules for every turn."""
    return """COMMUNICATION STYLE (every patient turn):
вЂў Speak SIMPLE Uzbek вЂ” words ordinary patients understand.
вЂў Be warm, professional, respectful, and natural вЂ” like Doctor Boysunov in a real clinic.
вЂў Never sound robotic, templated, or like ChatGPT.
вЂў Never ask duplicate questions вЂ” honor known_facts, topics_covered, and the full conversation.
вЂў Remember previous answers; synthesize before asking anything new.
вЂў Ask only the MINIMUM number of questions necessary for a safe, useful clinical conclusion.
вЂў Think, analyze, synthesize internally вЂ” then communicate clearly and humanly."""


def format_consultation_ending_rules() -> str:
    """Rules for structured closure and urgency-appropriate endings."""
    return """CONSULTATION SUMMARY (required when step7_ready_for_summary=true):
Populate consultation_closure with ALL fields:
  chief_complaint, clinical_summary, associated_symptoms, neurological_syndrome,
  most_likely_diagnosis, differential_diagnosis (ranked list), red_flags,
  recommended_investigations, treatment_strategy (general approach ONLY вЂ” no drug names/doses),
  next_step, urgent_referral_required, urgent_referral_reason.

CONSULTATION ENDING вЂ” patient_reply tone:

If NOT urgent (urgent_referral_required=false):
вЂў End politely and warmly. Include booking offer similar to:
  "Rahmat. Siz bergan ma'lumotlarga asoslanib dastlabki klinik xulosa tayyorlandi.
  Aniq tashxis va individual davolash rejasini tuzish uchun nevrolog ko'rigi muhim.
  Agar xohlasangiz, Doctor Boysunov bilan onlayn videokonsultatsiya yoki klinikadagi oflayn qabul uchun yozilishingiz mumkin.
  Sizga qaysi variant qulay bo'lsa, yozilishingizga yordam beraman."

If EMERGENCY (urgent_referral_required=true OR step4_emergency_assessment=urgent|emergency):
вЂў Do NOT recommend online consultation or routine appointment booking.
вЂў Immediately recommend emergency medical evaluation (103 / tez yordam or nearest shoshilinch yordam).
вЂў Safety first вЂ” urgent, clear, compassionate tone."""


def format_senior_neurologist_principles() -> str:
    """Core Phase 3 principles injected into GPT instructions."""
    return """SENIOR NEUROLOGIST CLINICAL INTELLIGENCE (Phase 3):
вЂў Think like Doctor Boysunov during a real clinic consultation вЂ” NOT ChatGPT, NOT a generic chatbot, NOT an intake form.
вЂў FIRST understand the patient's main complaint from their own words before asking anything.
вЂў ALWAYS prioritize dangerous neurological conditions (stroke, SAH, cauda equina, central vertigo, status epilepticus, meningitis) BEFORE routine history.
вЂў Ask ONLY the single highest-value question that would change differential or urgency вЂ” never low-yield or repeated questions.
вЂў Use explicit differential diagnosis reasoning; re-rank probabilities after EVERY new answer.
вЂў If multiple complaints exist, identify the DOMINANT complaint, explain why it leads, defer secondary complaints.
вЂў Adapt dynamically to age, medications, pregnancy, chronic disease, and every prior answer in this session.
вЂў Keep full consultation memory вЂ” never re-ask facts in known_facts, topics_covered, or conversation history.
вЂў Communicate with the patient in SIMPLE Uzbek (2вЂ“4 short sentences). Internal reasoning stays clinical and precise.
вЂў NEVER prescribe medications or dosages automatically. treatment_strategy = general approach pending in-person examination.
вЂў At closure (step7_ready_for_summary=true), fill consultation_closure completely and end with the appropriate urgency-based closing."""


def format_dominant_complaint_block(analysis: DominantComplaintAnalysis | None) -> str:
    if analysis is None:
        return ""
    lines = [
        "DOMINANT COMPLAINT ANALYSIS (use for this turn):",
        f"вЂў Dominant: {analysis.dominant_label} ({analysis.dominant_category})",
    ]
    if analysis.secondary_complaints:
        lines.append(f"вЂў Secondary (defer until dominant addressed): {', '.join(analysis.secondary_complaints)}")
    lines.append(f"вЂў Why dominant leads: {analysis.rationale}")
    return "\n".join(lines)


def _urgency_from_assessment(assessment: str, red_flags: list[str]) -> tuple[bool, str]:
    lowered = (assessment or "").lower()
    if lowered in {"emergency", "urgent", "shoshilinch", "103"} or red_flags:
        reason = "Qizil bayroqlar yoki favqulodda baho вЂ” zudlik bilan shifokor ko'rigi kerak."
        if any("103" in f.lower() or "tez yordam" in f.lower() for f in red_flags):
            reason = "103/TEZ yordam va shoshilinch nevrologik baholash kerak."
        return True, reason
    return False, ""


def _default_next_step(urgent: bool, assessment: str) -> str:
    if urgent or assessment in {"emergency", "urgent"}:
        return "Zudlik bilan shifokor ko'rigi yoki tez yordam. Keyin nevrolog konsultatsiyasi."
    return "Doctor Boysunov bilan onlayn yoki klinikada shaxsiy ko'rik tavsiya etiladi."


def _default_treatment_strategy(urgent: bool) -> str:
    if urgent:
        return "Shoshilinch tibbiy baholash вЂ” davolash rejasi shifokor ko'rigidan keyin."
    return "Aniq tashxis va individual davolash rejasi nevrolog ko'rigidan keyin belgilanadi."


def build_closure_summary(
    *,
    internal: ClinicalBrainInternal | Any,
    doctor_emr: DoctorEmrUpdate | None = None,
    dominant: DominantComplaintAnalysis | None = None,
    story: str = "",
) -> ConsultationClosureSummary:
    """Build structured end-of-consultation summary from internal reasoning."""
    ranked: list[RankedHypothesis] = []
    if hasattr(internal, "ranked_differential") and internal.ranked_differential:
        ranked = list(internal.ranked_differential)
    elif internal.step3_hypotheses:
        ranked = list(internal.step3_hypotheses)

    must_not_miss: list[RankedHypothesis] = []
    if hasattr(internal, "step3_must_not_miss"):
        must_not_miss = list(internal.step3_must_not_miss or [])

    red_flags = list(dict.fromkeys([*(internal.step4_red_flags or []), *(doctor_emr.red_flags_noted if doctor_emr else [])]))
    urgent, urgent_reason = _urgency_from_assessment(internal.step4_emergency_assessment, red_flags)

    clinical_parts: list[str] = []
    if story or getattr(internal, "story_synthesis", ""):
        clinical_parts.append(story or getattr(internal, "story_synthesis", ""))
    elif internal.step1_patient_meaning:
        clinical_parts.append(internal.step1_patient_meaning)
    if dominant:
        clinical_parts.append(f"Asosiy shikoyat: {dominant.dominant_label}.")

    ranked_labels = [
        f"{h.name} ({h.probability_pct}%)" if getattr(h, "probability_pct", 0) else f"{h.name} ({h.probability})"
        for h in ranked[:5]
        if h.name
    ]
    for h in must_not_miss[:3]:
        label = f"{h.name} (ajratib o'tilmasin)"
        if label not in ranked_labels:
            ranked_labels.append(label)

    most_likely = ranked_labels[0] if ranked_labels else ""
    differential = ranked_labels[1:] if len(ranked_labels) > 1 else []

    chief = (doctor_emr.chief_complaint if doctor_emr and doctor_emr.chief_complaint else "") or (
        dominant.dominant_label if dominant else ""
    )
    investigations = list(doctor_emr.recommended_investigations[:6]) if doctor_emr and doctor_emr.recommended_investigations else []

    recommended = _default_next_step(urgent, internal.step4_emergency_assessment)
    if investigations:
        inv = ", ".join(investigations[:3])
        recommended = f"{recommended} Tavsiya etilgan tekshiruvlar: {inv}."

    return ConsultationClosureSummary(
        chief_complaint=chief,
        clinical_summary=" ".join(clinical_parts).strip() or "Konsultatsiya davomida yig'ilgan ma'lumotlar tahlil qilindi.",
        associated_symptoms=[],
        neurological_syndrome=most_likely.split(" (")[0] if most_likely else "",
        most_likely_diagnosis=most_likely,
        differential_diagnosis=differential,
        ranked_diagnoses=ranked_labels,
        red_flags=red_flags,
        recommended_investigations=investigations,
        treatment_strategy=_default_treatment_strategy(urgent),
        recommended_next_step=recommended,
        urgent_referral_required=urgent,
        urgent_referral_reason=urgent_reason,
    )


def format_routine_consultation_ending() -> str:
    """Polite non-urgent closure вЂ” Doctor Boysunov booking offer."""
    return (
        "Rahmat. Siz bergan ma'lumotlarga asoslanib dastlabki klinik xulosa tayyorlandi.\n\n"
        "Aniq tashxis va individual davolash rejasini tuzish uchun nevrolog ko'rigi muhim.\n\n"
        "Agar xohlasangiz, Doctor Boysunov bilan:\n"
        "вЂў Onlayn videokonsultatsiya\n"
        "yoki\n"
        "вЂў Klinikadagi oflayn qabul\n"
        "uchun yozilishingiz mumkin.\n\n"
        "Sizga qaysi variant qulay bo'lsa, yozilishingizga yordam beraman."
    )


def format_emergency_consultation_ending(closure: ConsultationClosureSummary) -> str:
    """Emergency closure вЂ” no online booking."""
    reason = closure.urgent_referral_reason or "Holatingiz shoshilinch tibbiy baholashni talab qilishi mumkin."
    return (
        f"вљ пёЏ {reason}\n\n"
        "Iltimos, onlayn konsultatsiyani kechiktirmang вЂ” darhol 103 yoki eng yaqin shoshilinch yordamga murojaat qiling.\n"
        "Shoshilinch holatda onlayn yozilish tavsiya etilmaydi."
    )


def format_patient_closure_summary(closure: ConsultationClosureSummary) -> str:
    """Full patient-facing closure in simple Uzbek (for final reply body)."""
    lines: list[str] = []

    if closure.chief_complaint:
        lines.append(f"рџ“‹ Asosiy shikoyat: {closure.chief_complaint}")
    if closure.clinical_summary:
        lines.append(f"рџ“‹ Klinik xulosa: {closure.clinical_summary}")
    if closure.associated_symptoms:
        lines.append(f"рџ“‹ Qo'shimcha belgilar: {', '.join(closure.associated_symptoms[:5])}.")
    if closure.neurological_syndrome:
        lines.append(f"рџ“‹ Nevrologik sindrom: {closure.neurological_syndrome}")
    if closure.most_likely_diagnosis:
        lines.append(f"рџ”Ќ Eng ehtimoliy sabab (aniq tashxis emas): {closure.most_likely_diagnosis}.")
    dx = closure.differential_diagnosis or closure.ranked_diagnoses
    if dx:
        lines.append(f"рџ”Ќ Boshqa ehtimoliy sabablar: {'; '.join(dx[:4])}.")
    if closure.red_flags:
        lines.append(f"вљ пёЏ Diqqat вЂ” qizil bayroqlar: {', '.join(closure.red_flags[:3])}.")
    if closure.recommended_investigations:
        lines.append(f"рџ”¬ Tavsiya etilgan tekshiruvlar: {', '.join(closure.recommended_investigations[:4])}.")
    if closure.treatment_strategy:
        lines.append(f"рџ’Љ Davolash yo'nalishi: {closure.treatment_strategy}")
    if closure.recommended_next_step:
        lines.append(f"вћЎпёЏ Keyingi qadam: {closure.recommended_next_step}")

    summary_block = "\n".join(lines)
    if closure.urgent_referral_required:
        ending = format_emergency_consultation_ending(closure)
    else:
        ending = format_routine_consultation_ending()

    if summary_block:
        return f"{summary_block}\n\n{ending}"
    return ending


def format_brief_summary_for_help_menu(closure: ConsultationClosureSummary) -> str:
    """Short summary for help-menu intro (2 sentences max)."""
    parts: list[str] = []
    if closure.clinical_summary:
        parts.append(closure.clinical_summary[:200])
    if closure.urgent_referral_required:
        parts.append("Shoshilinch shifokor ko'rigi tavsiya etiladi.")
    elif closure.recommended_next_step:
        parts.append(closure.recommended_next_step[:120])
    return " ".join(parts[:2]).strip() or "Asosiy belgilaringizni inobatga oldim."


def merge_closure_from_response(
    data: dict[str, Any],
    internal: ClinicalBrainInternal | Any,
    doctor_emr: DoctorEmrUpdate | None,
    *,
    dominant: DominantComplaintAnalysis | None = None,
) -> ConsultationClosureSummary:
    """Prefer GPT consultation_closure; fall back to engine-built summary."""
    raw = data.get("consultation_closure") or {}
    if raw:
        closure = ConsultationClosureSummary.from_dict(raw)
        if (
            closure.clinical_summary
            or closure.most_likely_diagnosis
            or closure.differential_diagnosis
            or closure.ranked_diagnoses
        ):
            return closure
    return build_closure_summary(
        internal=internal,
        doctor_emr=doctor_emr,
        dominant=dominant,
        story=str(getattr(internal, "story_synthesis", "") or ""),
    )


def format_closure_emr_block(closure: ConsultationClosureSummary) -> str:
    lines = [
        "--- Senior Neurologist Closure (Phase 3) ---",
        f"Asosiy shikoyat: {closure.chief_complaint or 'вЂ”'}",
        f"Klinik xulosa: {closure.clinical_summary}",
    ]
    if closure.associated_symptoms:
        lines.append(f"Qo'shimcha belgilar: {', '.join(closure.associated_symptoms)}")
    if closure.neurological_syndrome:
        lines.append(f"Nevrologik sindrom: {closure.neurological_syndrome}")
    if closure.most_likely_diagnosis:
        lines.append(f"Eng ehtimoliy tashxis: {closure.most_likely_diagnosis}")
    dx = closure.differential_diagnosis or closure.ranked_diagnoses
    if dx:
        lines.append(f"Differensial tashxis: {'; '.join(dx)}")
    if closure.red_flags:
        lines.append(f"Qizil bayroqlar: {', '.join(closure.red_flags)}")
    if closure.recommended_investigations:
        lines.append(f"Tavsiya etilgan tekshiruvlar: {', '.join(closure.recommended_investigations)}")
    if closure.treatment_strategy:
        lines.append(f"Davolash strategiyasi: {closure.treatment_strategy}")
    lines.append(f"Keyingi qadam: {closure.recommended_next_step}")
    lines.append(f"Shoshilinch yo'llanma: {'Ha' if closure.urgent_referral_required else 'Yo\'q'}")
    if closure.urgent_referral_reason:
        lines.append(f"Sabab: {closure.urgent_referral_reason}")
    return "\n".join(lines)
