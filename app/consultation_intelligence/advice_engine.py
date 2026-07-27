"""AdviceEngine — personalized interim guidance from collected consultation facts."""

from __future__ import annotations

from app.consultation_intelligence.state import ConsultationState


def _lumbar_advice(state: ConsultationState, facts: dict[str, str]) -> list[str]:
    lines = [
        (
            "Hozirgi ma'lumotlaringizga ko'ra, bel-oyoq og'rig'i ko'pincha radikulopatiya "
            "(orqa umurtqadan chiqqan nerv bosilishi) bilan bog'liq bo'ladi."
        ),
        (
            "Uy sharoitida: qattiq yuzada uzoq o'tirmaslik, og'ir yuk ko'tarmaslik, "
            "qisqa yurishlar va belga issiq kompress qo'llash yordam berishi mumkin."
        ),
        (
            "Og'riq qoldiruvchi dorilar faqat shifokor tavsiyasi bilan — "
            "o'z-o'zidan kuchli dorilar ichmang."
        ),
    ]
    if any("radiation" in slug and val not in {"negative", ""} for slug, val in facts.items()):
        lines.insert(
            1,
            "Og'riq oyoqqa tarqalishi nerv yo'lining bosilishini ko'rsatishi mumkin — "
            "bu holatda harakatlarni sekinlashtirish muhim.",
        )
    return lines


def _headache_advice(state: ConsultationState, facts: dict[str, str]) -> list[str]:
    return [
        (
            "Bosh og'rig'i turli sabablarga bog'liq bo'lishi mumkin — migren, "
            "zarbali og'riq yoki boshqa sabablar."
        ),
        (
            "Uy sharoitida: tinch xona, yorug'likdan qochish, yetarli suyuqlik ichish "
            "va stressni kamaytirish yordam beradi."
        ),
        (
            "Agar bosh og'rig'i birdan eng kuchli darajada boshlansa, nutq yoki ko'rish buzilsa — "
            "bu darhol shifokorga murojaat qilishni talab qiladi."
        ),
    ]


def _neuropathy_advice(state: ConsultationState, facts: dict[str, str]) -> list[str]:
    return [
        (
            "Qo'l-oyoq uyuqligi va karaxtlik ko'pincha periferik neuropatiya "
            "(tashqi nervlarning shikastlanishi) bilan bog'liq bo'ladi."
        ),
        (
            "Uy sharoitida: qo'l-oyoqlarni issiq saqlash, qattiq batareyalardan qochish "
            "va oyoq kiyimlarini qulay tanlash tavsiya etiladi."
        ),
        "Qandli diabet yoki B12 yetishmovchiligi bo'lsa, ularni nazorat qilish muhim.",
    ]


def _secondary_note(state: ConsultationState) -> str | None:
    if not state.secondary_symptoms:
        return None
    labels = [str(s.get("label_uz") or "") for s in state.secondary_symptoms if s.get("label_uz")]
    if not labels:
        return None
    return f"Qo'shimcha belgilar ham qayd etildi: {', '.join(labels)}."


def generate_personalized_advice(state: ConsultationState) -> str:
    """Build advice from pathway, differential, and collected facts — no status boilerplate."""
    facts = state.fact_map()
    pathway = state.pathway_id
    lines: list[str] = []

    if pathway in ("lumbar_radiculopathy", "lumbar_spine"):
        lines.extend(_lumbar_advice(state, facts))
    elif pathway == "headache" or any(
        str(s.get("category")) == "headache" for s in state.secondary_symptoms
    ):
        lines.extend(_headache_advice(state, facts))
    elif "neuropathy" in pathway:
        lines.extend(_neuropathy_advice(state, facts))
    else:
        top = state.differential[0]["name"] if state.differential else state.syndrome_label_uz
        lines.append(
            f"Hozirgi ma'lumotlaringiz {state.syndrome_label_uz} yo'nalishida ko'rib chiqilmoqda."
        )
        if top:
            lines.append(f"Ehtimoliy yo'nalish: {top}.")
        lines.append(
            "Aniq davolash rejasi uchun yana bir necha muhim savolga javob kerak — "
            "keyin shifokor sizga mos reja tuzadi."
        )

    sec = _secondary_note(state)
    if sec:
        lines.insert(1, sec)

    if state.missing_information and len(state.missing_information) <= 3:
        lines.append(
            "To'liq reja uchun yana bir necha qisqa savolga javob kerak — "
            "javoblaringizdan keyin aniqroq yo'l ko'rsataman."
        )

    return "\n\n".join(lines)
