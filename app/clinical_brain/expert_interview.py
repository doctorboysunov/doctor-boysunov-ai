"""Expert neurologist interview strategy — high-yield priorities by complaint.

Used as reference for Clinical Brain GPT reasoning, NOT as a fixed script.
"""

from __future__ import annotations

from app.domain.consultation import ComplaintCategory

# Interview phases (priority logic, not fixed sequence)
PHASE_TRIAGE = "triage"
PHASE_NARRATIVE = "narrative"
PHASE_DISCRIMINATOR = "discriminator"
PHASE_CONTEXT = "context"
PHASE_CLOSURE = "closure"

_EXPERT_STRATEGIES: dict[ComplaintCategory, dict[str, str]] = {
    "headache": {
        "triage_first": (
            "SNOOP qizil bayroqlar: birdan boshlangan (Thunderclap), nevrologik belgi "
            "(nutq, ko'rish, kuchsizlik, hush), tizimli belgi (isitma, og'ir vazn yo'qotish), "
            "50+ yangi bosh og'rig'i, progressive/worsening pattern."
        ),
        "open_narrative": "Bemordan o'z so'zida hikoya oling: qachon, qanday boshlandi, qanday his qiladi.",
        "high_yield_discriminators": (
            "Boshlanish vaqti (birdan vs asta), lokalizatsiya, xarakter, qo'shimcha belgilar "
            "(ko'ngil aynishi, yorug'lik/sezgirlik), chastota, funksional ta'sir."
        ),
        "avoid_early": (
            "1-10 shkalasi yoki juda tor savollarni birinchi navbatda bermang. "
            "Avval hikoya va xavfsizlik skriningi."
        ),
        "expert_first_question": "Birdan boshlandimi yoki asta asta kuchayaptimi? Qo'shimcha belgilar bormi?",
    },
    "low_back_pain": {
        "triage_first": (
            "Cauda equina / shoshilinch: ikkala oyoq kuchsizligi, sezgi yo'qolishi (saddle), "
            "ishlash/qayta tutib bo'lmaslik, travma, isitma, IV dori qabul qilish, saraton tarixi."
        ),
        "open_narrative": "Og'riq qayerda, qachondan, nima qilib kuchayadi/yengillaydi — bemor hikoyasi.",
        "high_yield_discriminators": (
            "Nur radiatsiyasi (iqtiroiyog'riq), uzoq yurishda yengillashish (spinal stenoz), "
            "tungi og'riq, progressive defitsit."
        ),
        "avoid_early": "Boshlang'ichda faqat 'qancha og'riyapti 1-10' bermang — funksiya va red flag muhimroq.",
        "expert_first_question": "Oyoq yoki oyoqlaringizda kuchsizlik yoki sezgi o'zgarishi bormi?",
    },
    "neck_pain": {
        "triage_first": (
            "Qo'shimcha bosh og'rig'i, ko'rish buzilishi, nutq muammosi, qo'l oyoq kuchsizligi, "
            "isitma, travma — myelopatiya / disseksiya / meningit belgilari."
        ),
        "open_narrative": "Bo'yin og'rig'i qachondan, qanday boshlangan, qayerga tarqaladi.",
        "high_yield_discriminators": "Radiatsiya (qo'l), uyuqish, bosh harakati cheklanganligi, Lhermitte.",
        "avoid_early": "Faqat lokalizatsiya so'ramang — myelopatiya skriningi muhim.",
        "expert_first_question": "Qo'l yoki oyoqlarda uyuqish yoki kuchsizlik sezdingizmi?",
    },
    "vertigo": {
        "triage_first": (
            "Doimiy vertigo + bosh og'rig'i/nutq/koordinatsiya → markaziy sabab. "
            "Yangi eshitish yo'qolishi, qo'l-oyoq kuchsizligi."
        ),
        "open_narrative": "Bosh aylanishi doimiymi yoki hujum (epizod) bo'lib keladimi?",
        "high_yield_discriminators": (
            "Epizod davomiyligi (sekund vs soat), pozitsionallik (BPPV), eshitish, "
            "tinnitus, yurak urishi, stress."
        ),
        "avoid_early": "Birinchi savol 'qachondan' emas — timing pattern (epizod vs doimiy) eng muhim ajratuvchi.",
        "expert_first_question": "Bosh aylanishi doimiy turadimi yoki ayrim paytlarda hujum qilib keladimi?",
    },
    "stroke": {
        "triage_first": "Vaqt muhim: oxirgi marta sog'lom qachon (last well). 103/TEZ yordam.",
        "open_narrative": "Aniq belgilar: yuz, qo'l, nutq — qachon boshlangan.",
        "high_yield_discriminators": "Antikoagulyant, travma, qandli diabet, qon bosimi.",
        "avoid_early": "Uzoq anamnez bermang — vaqt va belgi lokalizatsiyasi birinchi.",
        "expert_first_question": "Belgi qachon aniq boshlangan? Hozir qo'l yoki nutqda muammo bormi?",
    },
    "neuropathy": {
        "triage_first": "Tez progressiya, faqat bir tomonda, orqa og'riq bilan — shoshilinch emasmi tekshiring.",
        "open_narrative": "Uyuqish/qiynish qayerda, qachondan, qanday tarqalgan.",
        "high_yield_discriminators": "Simmetrik vs asimmetrik, diabet, alkogol, dori, tungi yomonlashish.",
        "avoid_early": "Birinchi savol 'qaysi tomonda' dan oldin simmetriya va progressiya.",
        "expert_first_question": "Ikki tomonda ham shundaymi yoki faqat bir tomonda?",
    },
    "facial_nerve_palsy": {
        "triage_first": "Butun yuz vs faqat pastki yuz (insult ajratish), quloq og'rig'i, chuqur og'riq.",
        "open_narrative": "Qachon boshlangan, qanday kechgan (kuchayaptimi).",
        "high_yield_discriminators": "Ko'z quruqligi, ta'm buzilishi, quloq shiltillash.",
        "avoid_early": "Darhol 'insult' deb qo'rqitmang — ajratuvchi belgilarni so'rang.",
        "expert_first_question": "Butun yuz harakatsizmi yoki faqat pastki qismi?",
    },
    "tremor": {
        "triage_first": "Yangi tez kuchaygan, bosh og'rig'i/belgi bilan — ikkinchi darajali sabab.",
        "open_narrative": "Titroq qachondan, qachon ko'proq (dam olish/da harakat).",
        "high_yield_discriminators": "Istirahat vs harakat, bir tomondimi, dori, alkogol yaxshilaydimi.",
        "avoid_early": "Birinchi savol 'qachondan' bo'lishi mumkin lekin rest vs action muhim.",
        "expert_first_question": "Titroq dam olganda ko'proqmi yoki harakat qilganda?",
    },
    "memory_problems": {
        "triage_first": "Tez boshlangan, bosh og'rig'i/fever, nutq — delirium/infeksiya.",
        "open_narrative": "Bemor va yaqinlari nima sezgan — qanday xotira muammosi.",
        "high_yield_discriminators": "Kunduzgi hayotga ta'sir, orientatsiya, dori, uyqu, mood.",
        "avoid_early": "Test savollari bermang — funksional ta'sir va boshlanish muhim.",
        "expert_first_question": "Kundalik ishlar (pul, dori, yo'l topish) qiyinlashdimi?",
    },
    "sleep_disorders": {
        "triage_first": "Qattiq uxlab qolish, hushdan ketish, tungi havo yetishmovchiligi.",
        "open_narrative": "Uyqu muammosi qanday: uxlay olmaslik, erta uyg'onish, qattiq uxlab qolish.",
        "high_yield_discriminators": "Xroniklik, qandli diabet og'irligi, xavotir, qon bosimi.",
        "avoid_early": "Umumiy 'uyqu qanday' o'rniga aniq tip ajratish.",
        "expert_first_question": "Asosan uxlay olmayapsizmi, tez uyg'onasizmi yoki kunduz charchoq bormi?",
    },
    "anxiety": {
        "triage_first": "Fizik belgilar (ko'krak og'rig'i, nafas) — organik sababni istisno qilish.",
        "open_narrative": "Xavotir qachondan, nima paydo bo'ladi.",
        "high_yield_discriminators": "Panik hujum, uyqu, somatik belgilar, funksiya.",
        "avoid_early": "Psixologik savollarni tibbiy skriningdan oldin bermang.",
        "expert_first_question": "Xavotir bilan birga jismoniy belgilar (yurak urishi, nafas) bormi?",
    },
    "depression": {
        "triage_first": "O'z joniga qasd fikri, psixotik belgilar — xavfsizlik.",
        "open_narrative": "Kayfiyat qachondan, qanday ta'sir.",
        "high_yield_discriminators": "Uyqu, ishtaha, energiya, nevrologik belgi bormi.",
        "avoid_early": "Darhol dori tavsiya qilmang — xavfsizlik va somatik overlap.",
        "expert_first_question": "Oxirgi haftalarda kunduz hayotda nima o'zgardi?",
    },
    "other_neurological": {
        "triage_first": "Yangi yoki tez kuchaygan belgilar, ong, nafas, ko'krak og'rig'i.",
        "open_narrative": "Bemordan erkin hikoya oling — nima bezovta qilyapti.",
        "high_yield_discriminators": "Vaqt, progressiya, funksional ta'sir.",
        "avoid_early": "Aniq kategoriya yo'q — ochiq savol + xavfsizlik.",
        "expert_first_question": "Muammoingizni o'z so'zingiz bilan qisqacha ayting — qachondan?",
    },
}


def get_expert_interview_strategy(category: ComplaintCategory) -> dict[str, str]:
    return _EXPERT_STRATEGIES.get(category, _EXPERT_STRATEGIES["other_neurological"])


def format_presentation_overrides(message: str) -> str:
    """Keyword-triggered expert hints when classifier category is too broad."""
    lowered = message.lower()
    if "aylan" in lowered and any(w in lowered for w in ("doimiy", "yiqil", "yurishda")):
        return (
            "PRESENTATION OVERRIDE — continuous vertigo with imbalance: screen central causes "
            "(stroke, cerebellar) before peripheral ear questions."
        )
    if any(w in lowered for w in ("ishlamayapti", "nutqim buzildi", "falaj", "insult", "qo'lim", "qo‘lim")):
        return (
            "PRESENTATION OVERRIDE — possible acute stroke/TIA: time of onset, last known well, "
            "current deficits — MINIMAL questions, urgent assessment."
        )
    if any(w in lowered for w in ("hushimdan", "tutqanoq", "convulsion", "seizure", "tilim qisil")):
        return (
            "PRESENTATION OVERRIDE — possible seizure: prioritize witness account, duration, "
            "post-ictal confusion, tongue bite, incontinence, fever, alcohol/meds, first vs recurrent."
        )
    if any(w in lowered for w in ("eng kuchli", "birdan qattiq", "thunderclap")):
        return (
            "PRESENTATION OVERRIDE — thunderclap headache: prioritize sudden onset to peak, "
            "worst-ever, meningism, neuro deficit — NOT location/character first."
        )
    if any(w in lowered for w in ("hojatxonaga qiyin", "siydik", "cauda")):
        return (
            "PRESENTATION OVERRIDE — cauda equina concern: bilateral leg symptoms, saddle numbness, "
            "urinary retention — urgent before chronicity questions."
        )
    return ""


def format_expert_strategy_block(category: ComplaintCategory, *, topics_covered: list[str], message: str = "") -> str:
    strategy = get_expert_interview_strategy(category)
    covered = set(topics_covered or [])
    triage_done = any(t in covered for t in ("triage", "red_flags", "emergency_screen", "snoop"))
    lines = [
        "SENIOR NEUROLOGIST CLINICAL INTELLIGENCE — interview strategy (reasoning guide — adapt to patient):",
    ]
    override = format_presentation_overrides(message)
    if override:
        lines.append(f"• {override}")
    lines.extend([
        f"• Triage first: {strategy['triage_first']}",
        f"• Open narrative: {strategy['open_narrative']}",
        f"• High-yield discriminators: {strategy['high_yield_discriminators']}",
        f"• Avoid too early: {strategy['avoid_early']}",
    ])
    if not topics_covered:
        lines.append(f"• Typical expert opening focus: {strategy['expert_first_question']}")
    elif not triage_done:
        lines.append("• Triage screening NOT yet documented — prioritize safety screen before detail questions.")
    else:
        lines.append("• Triage addressed — move to narrative or high-yield discriminators.")
    lines.append(
        "Interview phases (choose ONE question from the highest-priority incomplete phase): "
        "triage → narrative → discriminator → context → closure. "
        "If multiple complaints in one message, address the dominant complaint first and explain why."
    )
    return "\n".join(lines)


def suggest_interview_phase(
    category: ComplaintCategory,
    *,
    topics_covered: list[str],
    message: str,
    detected_red_flags: list[str],
) -> str:
    """Heuristic phase hint for evaluation rubric (not a hard rule)."""
    covered = set(topics_covered or [])
    if detected_red_flags or any(w in message.lower() for w in ("birdan", "eng kuchli", "hush", "falaj", "103")):
        return PHASE_TRIAGE
    if not covered or covered <= {"opening_complaint"}:
        return PHASE_TRIAGE if category in {"headache", "stroke", "low_back_pain", "vertigo"} else PHASE_NARRATIVE
    if "onset" not in covered and "narrative" not in covered:
        return PHASE_NARRATIVE
    if len(covered) < 4:
        return PHASE_DISCRIMINATOR
    return PHASE_CONTEXT
