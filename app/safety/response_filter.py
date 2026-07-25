"""Post-process AI responses to enforce medical safety."""

from __future__ import annotations

import re

CONSULTATION_CTA = (
    "Aniq tashxis va davolash rejasi uchun Doctor Boysunov bilan "
    "onlayn yoki offline konsultatsiya bron qiling."
)

PRESCRIPTION_PATTERNS = (
    r"\b\d+\s*(mg|ml|g|mcg|meq)\b",
    r"\b\d+\s*(tablet|tabletk|kapsul|pill)\b",
    r"\bkuniga\s+\d+",
    r"\bretsept\b",
    r"\bprescri",
    r"\btake\s+\d+",
    r"\bparacetamol\b.*\b\d+",
    r"\bibuprofen\b.*\b\d+",
    r"\bantibiotik\b.*\b(qabul|iching|olin)",
    r"\bdori.*\b(kuniga|doza|mg|ml)\b",
)

DEFINITIVE_DIAGNOSIS_PATTERNS = (
    r"\bsizda\s+.+\s+(bor|kasalligi bor|diagnost)",
    r"\baniq tashxis",
    r"\bdefinitive diagnosis\b",
    r"\byou have\s+(been diagnosed|a confirmed)",
    r"\b100%\s+(sure|ishonch)",
    r"\b(o['']?zingizda|sizda)\s+.+\s+kasallik\b",
)

EXAM_REPLACEMENT_PATTERNS = (
    r"\b(shifokor|doctor).{0,60}(kerak emas|shart emas|o['']?rnini bos)",
    r"\bno need (for|to see) a doctor\b",
    r"\bdoctor examination is not needed\b",
    r"\binstead of (seeing|visiting) a doctor\b",
)

UNSAFE_COMBINED = PRESCRIPTION_PATTERNS + DEFINITIVE_DIAGNOSIS_PATTERNS + EXAM_REPLACEMENT_PATTERNS


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def classify_response_violations(response: str) -> list[str]:
    violations: list[str] = []
    if _matches_any(response, PRESCRIPTION_PATTERNS):
        violations.append("prescription_or_dosage")
    if _matches_any(response, DEFINITIVE_DIAGNOSIS_PATTERNS):
        violations.append("definitive_diagnosis")
    if _matches_any(response, EXAM_REPLACEMENT_PATTERNS):
        violations.append("replaces_examination")
    return violations


def build_safe_educational_fallback(user_message: str, violations: list[str]) -> str:
    topic_hint = user_message.strip().rstrip(".")
    if len(topic_hint) > 120:
        topic_hint = topic_hint[:117] + "..."

    return (
        "Bu savol tibbiy jihatdan nozik. Men faqat umumiy ma'lumot bera olaman — "
        "dori-darmon, dozalar yoki retsept yozib bera olmayman va aniq tashxis qo'yolmayman.\n\n"
        f"Sizning savolingiz: \"{topic_hint}\"\n\n"
        "Umumiy ma'lumot: alomatlar ko'p sabablarga bog'liq bo'lishi mumkin. "
        "Aniq baholash uchun shifokor ko'rigidan o'tish muhim.\n\n"
        f"{CONSULTATION_CTA}"
    )


def sanitize_ai_response(user_message: str, response: str) -> tuple[str, list[str]]:
    violations = classify_response_violations(response)
    if not violations:
        if CONSULTATION_CTA.lower() not in response.lower() and _should_add_consultation_cta(user_message):
            return f"{response.rstrip()}\n\n{CONSULTATION_CTA}", violations
        return response, violations

    return build_safe_educational_fallback(user_message, violations), violations


def _should_add_consultation_cta(user_message: str) -> bool:
    text = user_message.lower()
    triggers = (
        "davolanish",
        "dori",
        "retsept",
        "tashxis",
        "diagnoz",
        "treatment",
        "prescri",
        "kasallik",
        "og'riq",
    )
    return any(token in text for token in triggers)
