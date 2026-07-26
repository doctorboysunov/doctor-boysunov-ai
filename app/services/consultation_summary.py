"""Generate structured medical consultation summaries from collected answers."""

from __future__ import annotations

import re

from app.domain.consultation import ComplaintCategory, ConsultationSummary
from app.services.consultation_classifier import complaint_label

_CATEGORY_DIFFERENTIALS: dict[ComplaintCategory, list[str]] = {
    "headache": [
        "Tension-type bosh og'rig'i",
        "Migren",
        "Klaster bosh og'rig'i",
        "Sinusitga bog'liq bosh og'rig'i",
        "Ikkinchi darajali sabablar (qon bosimi, infeksiya)",
    ],
    "low_back_pain": [
        "Mushak-ligament bel og'rig'i",
        "Disk herniyasi / radikulopatiya",
        "Spinal stenoz",
        "Spondiloartroz",
    ],
    "neck_pain": [
        "Servikal miopatiya",
        "Servikal disk patologiyasi",
        "Servikal radikulopatiya",
        "Meningeal belgilar (infeksiya xavfi)",
    ],
    "vertigo": [
        "BPPV (benign paroksismal pozitsion vertigo)",
        "Vestibulyar neyrit",
        "Meniere kasalligi",
        "Markaziy sabablar (insult, demyelinizatsiya)",
    ],
    "stroke": [
        "Ishemik insult",
        "Gemorragik insult",
        "TIA (vaqtinchalik ishemik hujum)",
    ],
    "neuropathy": [
        "Diabetik neuropatiya",
        "Kompressiv neuropatiya (karpal tunnel va h.k.)",
        "Polineyropatiya",
        "Radikulopatiya",
    ],
    "facial_nerve_palsy": [
        "Bell palsy",
        "Sentral yuz falaji (insult xavfi)",
        "Infeksion/tumor sababli yuz falaji",
    ],
    "tremor": [
        "Essensial tremor",
        "Parkinson kasalligi",
        "Dori-indutsirovlangan tremor",
        "Tirotoksikoz",
    ],
    "memory_problems": [
        "Yengil kognitiv buzilish",
        "Demensiya spektri",
        "Depressiyaga bog'liq kognitiv buzilish",
        "Metabolik/endokrin sabablar",
    ],
    "sleep_disorders": [
        "Insomnia",
        "Uyqu apnoe sindromi",
        "Tsirkadiyan ritm buzilishi",
        "Depressiya/anxiety bilan bog'liq uyqu buzilishi",
    ],
    "anxiety": [
        "Generalized anxiety disorder",
        "Panik buzilish",
        "Somatik shikoyatlar bilan anxiety",
    ],
    "depression": [
        "Depressiv buzilish",
        "Bipolar buzilish (depressiv faz)",
        "Organik sababli kayfiyat buzilishi",
    ],
    "other_neurological": [
        "Nevrologik konsultatsiya talab qiluvchi shikoyat",
        "Somatik-nevrologik buzilish",
    ],
}

_CATEGORY_INVESTIGATIONS: dict[ComplaintCategory, list[str]] = {
    "headache": ["Qon bosimi", "Ko'rish tekshiruvi", "Kerak bo'lsa MRI bosh/moyoq"],
    "low_back_pain": ["Nevrologik status", "MRI bo'yin/bel bo'limi (ko'rsatma bo'yicha)"],
    "neck_pain": ["Nevrologik status", "Servikal rentgen/MRI (ko'rsatma bo'yicha)"],
    "vertigo": ["Nevrologik va vestibulyar tekshiruv", "Eshitish tekshiruvi", "MRI (markaziy sabab shubhasi)"],
    "stroke": ["Zudlik bilan CT/MRI miya", "Qon tahlillari", "Qon bosimi monitoring"],
    "neuropathy": ["Qandlik", "B12", "EMG/ENMG (ko'rsatma bo'yicha)"],
    "facial_nerve_palsy": ["Yuz va nevrologik ko'rik", "Kerak bo'lsa MRI"],
    "tremor": ["Nevrologik ko'rik", "TSH, qon tahlillari", "Kerak bo'lsa MRI"],
    "memory_problems": ["Kognitiv skrining", "B12, TSH", "MRI (ko'rsatma bo'yicha)"],
    "sleep_disorders": ["Uyqu anamnezi", "Polisomnografiya (apnoe shubhasi)", "Depressiya/anxiety skrining"],
    "anxiety": ["Klinik baholash", "Qon bosimi/EKG (jismoniy belgilar bo'lsa)"],
    "depression": ["Klinik baholash", "O'z joniga qasd xavfi skriningi"],
    "other_neurological": ["Nevrologik ko'rik", "Laboratoriya va tasvir tekshiruvlari (ko'rsatma bo'yicha)"],
}


def _answer(session_answers: dict[str, str], key: str, default: str = "ko'rsatilmagan") -> str:
    value = session_answers.get(key, "").strip()
    return value if value else default


def _extract_severity(answers: dict[str, str]) -> int | None:
    raw = answers.get("severity", "")
    match = re.search(r"(\d{1,2})", raw)
    if match:
        value = int(match.group(1))
        if 1 <= value <= 10:
            return value
    return None


def _derive_urgency(
    category: ComplaintCategory,
    answers: dict[str, str],
    red_flags: list[str],
) -> str:
    if red_flags or category == "stroke":
        return "emergency"
    severity = _extract_severity(answers)
    if severity is not None and severity >= 8:
        return "urgent"
    progression = _answer(answers, "progression", "").lower()
    if any(word in progression for word in ("yomonlash", "kuchay", "worse")):
        return "urgent"
    return "routine"


def _derive_visit_type(urgency: str) -> str:
    if urgency == "emergency":
        return "Shoshilinch yordam (103), keyin shifokor konsultatsiyasi"
    if urgency == "urgent":
        return "Tez kunda shaxsiy (offline) nevrolog qabuli"
    return "Onlayn yoki offline nevrolog konsultatsiyasi"


def _build_history(category: ComplaintCategory, answers: dict[str, str]) -> str:
    parts: list[str] = []
    for key, value in sorted(answers.items()):
        if value.strip():
            parts.append(f"{key}: {value.strip()}")
    label = complaint_label(category)
    return f"{label}. " + "; ".join(parts[:6]) if parts else label


def _build_timeline(answers: dict[str, str]) -> str:
    onset = _answer(answers, "onset") or _answer(answers, "stroke_onset")
    progression = _answer(answers, "progression", "")
    if progression and progression != "ko'rsatilmagan":
        return f"Boshlanish: {onset}. Dinamika: {progression}."
    return f"Boshlanish: {onset}."


def _build_risk_factors(answers: dict[str, str]) -> list[str]:
    risks: list[str] = []
    chronic = _answer(answers, "chronic_conditions", "")
    if chronic and chronic != "ko'rsatilmagan":
        risks.append(chronic)
    injury = _answer(answers, "back_injury", "")
    if injury and injury != "ko'rsatilmagan" and "yo'q" not in injury.lower():
        risks.append(f"Jarohat/travma: {injury}")
    triggers = _answer(answers, "headache_triggers", "") or _answer(answers, "anxiety_triggers", "")
    if triggers and triggers != "ko'rsatilmagan":
        risks.append(f"Trigger: {triggers}")
    return risks


def _build_follow_up(urgency: str, category: ComplaintCategory) -> str:
    if urgency == "emergency":
        return "Avvalo shoshilinch yordam. Stabilizatsiyadan keyin nevrolog bilan qayta baholash."
    if urgency == "urgent":
        return "24–72 soat ichida shaxsiy nevrolog qabuli va kerakli tasvir tekshiruvlari."
    return (
        f"{complaint_label(category)} bo'yicha onlayn yoki klinikada konsultatsiya. "
        "Simptomlar kuchaysa darhol murojaat qiling."
    )


def generate_consultation_summary(
    category: ComplaintCategory,
    answers: dict[str, str],
    *,
    red_flags: list[str] | None = None,
) -> ConsultationSummary:
    flags = list(red_flags or [])
    urgency = _derive_urgency(category, answers, flags)
    visit_type = _derive_visit_type(urgency)
    differentials = list(_CATEGORY_DIFFERENTIALS.get(category, []))
    investigations = list(_CATEGORY_INVESTIGATIONS.get(category, []))

    severity = _extract_severity(answers)
    if severity is not None and severity >= 7 and "Yuqori intensivlik" not in differentials:
        differentials.insert(0, "Yuqori intensivlik — boshqa sabablarni istisno qilish kerak")

    return ConsultationSummary(
        chief_complaint=complaint_label(category),
        history=_build_history(category, answers),
        timeline=_build_timeline(answers),
        risk_factors=_build_risk_factors(answers),
        red_flags=flags,
        possible_differential_diagnoses=differentials[:5],
        recommended_investigations=investigations,
        urgency=urgency,
        recommended_visit_type=visit_type,
        follow_up_plan=_build_follow_up(urgency, category),
    )
