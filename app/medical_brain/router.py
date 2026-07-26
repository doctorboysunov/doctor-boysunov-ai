"""Specialty routing — identify primary and secondary specialties from patient message."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.medical import MedicalSpecialty
from app.medical_brain.specialties.definitions import MULTI_SPECIALTY_HINTS, SPECIALTY_DEFINITIONS
from app.services.consultation_classifier import classify_complaint


@dataclass
class SpecialtyRouting:
    primary: MedicalSpecialty
    secondary: list[MedicalSpecialty] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    confidence: str = "low"
    is_emergency: bool = False
    reasoning: str = ""

    @property
    def all_specialties(self) -> list[MedicalSpecialty]:
        return [self.primary, *self.secondary]


def _score_specialties(text: str) -> dict[MedicalSpecialty, int]:
    normalized = (text or "").strip().lower()
    scores: dict[MedicalSpecialty, int] = {}
    for module in SPECIALTY_DEFINITIONS:
        score = 0
        for pattern in module.patterns:
            if re.search(pattern, normalized):
                score += 1
        if score:
            scores[module.id] = score + (module.priority // 20)
    return scores


def _apply_multi_specialty_hints(text: str, scores: dict[MedicalSpecialty, int]) -> None:
    normalized = (text or "").strip().lower()
    for patterns, specialties in MULTI_SPECIALTY_HINTS:
        if all(re.search(p, normalized) for p in patterns):
            for i, specialty in enumerate(specialties):
                boost = 3 - i
                scores[specialty] = scores.get(specialty, 0) + boost  # type: ignore[literal-required]


def _apply_coordination_rules(text: str, primary: MedicalSpecialty, secondary: list[MedicalSpecialty]) -> list[MedicalSpecialty]:
    """Add clinically required secondary specialties."""
    normalized = (text or "").strip().lower()
    extras: list[MedicalSpecialty] = list(secondary)

    def _add(spec: MedicalSpecialty) -> None:
        if spec != primary and spec not in extras:
            extras.insert(0, spec)

    if primary == "cardiology" or re.search(r"ko['']?krak|chest pain", normalized):
        _add("emergency_medicine")

    if primary == "neurology" and re.search(
        r"insult|stroke|falaj|kuchsiz|nutq.*buzil|yarim tan|tutqanoq|hush.*ket|seizure|"
        r"eng kuchli|birdan juda.*bosh|doimiy bosh aylan",
        normalized,
    ):
        _add("emergency_medicine")

    if re.search(r"diabet|qandli diabet", normalized) and re.search(r"uvyapti|uvish", normalized):
        if primary == "endocrinology":
            _add("neurology")
        elif primary == "neurology":
            _add("endocrinology")

    if primary == "general_surgery" and re.search(r"qorin.*og['']?ri|qattiq", normalized):
        _add("emergency_medicine")
        _add("gastroenterology")

    if re.search(r"nafas qis|nafas olish.*qiyin|hemoptysis|qon tuflay|qon chiqyapti", normalized):
        if not re.search(r"zinadan|shishadi|orto", normalized):
            _add("emergency_medicine")
        if primary == "pulmonology":
            _add("cardiology")

    if re.search(r"hush.*ket|syncope|birdan hush", normalized):
        _add("emergency_medicine")
        if primary != "cardiology":
            _add("cardiology")
        _add("neurology")

    if re.search(r"shishgan.*issiq|issiq.*shish|bog['']?im.*shish", normalized):
        _add("emergency_medicine")
        if primary == "orthopedics":
            return ["rheumatology", *extras]

    if re.search(r"oyoq.*kuchsiz|kuchsiz.*tarqal|yuqoridan pastga", normalized):
        _add("emergency_medicine")

    if re.search(r"o['']?z joniga|suicid|o['']?zini o['']?ldir", normalized):
        _add("emergency_medicine")

    if re.search(r"ko['']?z.*og['']?ri|ko['']?ngil ayni.*ko['']?z|halqa ko['']?raman", normalized):
        _add("emergency_medicine")

    if re.search(r"ko['']?krak.*kuydirish|reflyuks|ovqatdan keyin.*kuydirish", normalized):
        if primary == "gastroenterology":
            _add("cardiology")
        if re.search(r"nafas|zinadan", normalized):
            _add("cardiology")

    if re.search(r"qandli diabet.*ko['']?rish|diabet.*ko['']?rish|ko['']?rish.*diabet", normalized):
        _add("ophthalmology")
        _add("endocrinology")

    if re.search(r"yiqil|yurak.*dori|polypharmacy|ko['']?p dori", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")

    if re.search(r"tabletka ichib|paracetamol|overdose", normalized):
        _add("gastroenterology")

    if re.search(r"tomoq og['']?ri.*yutish|yutish qiyin.*tomoq", normalized):
        _add("emergency_medicine")
        _add("infectious_diseases")

    if re.search(r"terisi.*qizarib|limfa.*shish|tomoqchalar", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")
        _add("pulmonology")
        _add("ophthalmology")

    if re.search(r"eng kuchli og['']?riq|hayotimdagi eng kuchli|birdan juda qattiq.*bosh|birdan boshlandi va juda kuchli", normalized):
        _add("emergency_medicine")

    if re.search(r"qorin yuqori.*bel|belga tarqal|pankreatit", normalized):
        _add("emergency_medicine")

    if re.search(r"Crohn|qon aralash|8 marta.*axlat", normalized):
        _add("emergency_medicine")

    if re.search(r"qattiq og['']?riq.*qorin past|qorin past.*o['']?tkir|torsion|moyak.*birdan|birdan boshlandi.*qus", normalized):
        _add("emergency_medicine")

    if re.search(r"o['']?ldirmoqchi|suicid|panika|o['']?lim qo['']?rqu", normalized):
        _add("emergency_medicine")

    if re.search(r"xotira yomon.*isitma|xulq o['']?zgar.*isitma", normalized):
        _add("emergency_medicine")

    if re.search(r"birdan boshlandi.*kuchli|juda kuchli.*ko['']?ngil", normalized):
        _add("emergency_medicine")

    if primary == "neurology" and re.search(r"birdan|juda kuchli|eng kuchli", normalized):
        _add("emergency_medicine")

    if re.search(r"belda o['']?tir|belda o['']?tkir|bel.*o['']?tkir|tizza og['']?ri.*qusish|renal colic|siydikda qon", normalized):
        _add("urology")

    if re.search(r"hayz.*ko['']?p qon|qon kam|tez charchayman", normalized):
        _add("gynecology")
        if primary != "internal_medicine":
            _add("internal_medicine")

    if re.search(r"ovozim|ovoz.*xira", normalized):
        _add("oncology")

    if re.search(r"ko['']?p ichaman.*ko['']?p siyaman|nafas.*meva hid", normalized):
        _add("emergency_medicine")

    if re.search(r"oyoq.*kuchsiz|kuchsiz.*tarqal", normalized):
        _add("emergency_medicine")

    if re.search(r"quloq eshitmay|eshitish.*yo['']?qol", normalized):
        _add("emergency_medicine")

    if re.search(r"ko['']?z.*ko['']?rmay|parda tush|chaqnash", normalized):
        _add("emergency_medicine")

    if re.search(r"isitma.*topilmadi|tungi terlash|safar.*isitma", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")
        _add("infectious_diseases")

    if re.search(r"xotira yomon|xulq o['']?zgardi|confus", normalized):
        _add("neurology")
        _add("infectious_diseases")

    if re.search(r"tabletka ichib|ko['']?p tabletka", normalized):
        _add("psychiatry")

    if re.search(r"avtohalokat|halokat|travma|jarohat|yiqilib tush", normalized):
        _add("emergency_medicine")
        if primary != "orthopedics":
            _add("orthopedics")
        if re.search(r"ko['']?krak|qorin|qo['']?l|bilak|tizza", normalized):
            _add("general_surgery")

    if re.search(r"javob bermayapti|boshqacha|hushsiz|onam hushsiz|confus|hush.*ket|hushdan ket", normalized):
        _add("emergency_medicine")
        _add("neurology")
        if re.search(r"isitma|siydik|fever|hidli|38\.", normalized):
            _add("infectious_diseases")

    if re.search(r"tabletka ichib|ko['']?p tabletka|overdose|o['']?z joniga", normalized):
        _add("emergency_medicine")
        _add("psychiatry")

    if re.search(r"homilador.*qon|homiladorman.*qon|ectopic", normalized):
        _add("emergency_medicine")

    if re.search(r"shakar tush|giperglikem|titroq.*terlash", normalized):
        _add("emergency_medicine")

    if re.search(r"qorong['']?u axlat|qon.*axlat|qattiq qorin og['']?ri|moyak og['']?ri.*birdan", normalized):
        _add("emergency_medicine")

    if re.search(r"qorin o['']?ng past|appendicitis|apend|o['']?ng pastga", normalized):
        _add("emergency_medicine")

    if re.search(r"homiladorlik testi ijobiy|ectopic", normalized):
        _add("emergency_medicine")

    if re.search(r"bola.*tutqanoq|tutqanoq tutdi", normalized):
        _add("emergency_medicine")
        _add("neurology")

    if re.search(r"bola.*qus|ichmayapti.*kam siydiyapti", normalized):
        _add("emergency_medicine")

    if re.search(r"qorin past", normalized):
        if primary != "gynecology":
            _add("gynecology")

    if re.search(r"bel og['']?ri", normalized) and re.search(r"hojatxonaga|siydik tut|oyoq.*uysin|uviydi", normalized):
        _add("emergency_medicine")
        _add("urology")

    if re.search(r"oyoq.*kuchsiz.*yuqoriga|kuchsiz.*tarqal|yuqoriga ko['']?taril", normalized):
        _add("emergency_medicine")
        if primary != "neurology":
            _add("neurology")

    if re.search(r"qayta yutish|yutolmayapti.*o['']?tirganda|ko['']?z qism.*tush", normalized):
        _add("emergency_medicine")
        if primary != "neurology":
            _add("neurology")

    if re.search(r"yuz qizar.*qon bosim|qon bosim 200|paroksism", normalized):
        _add("emergency_medicine")
        _add("cardiology")

    if re.search(r"ko['']?krak.*kuydirish|kuydirish.*ko['']?krak|ovqatdan keyin.*og['']?riq", normalized):
        if primary != "gastroenterology":
            _add("gastroenterology")
        _add("cardiology")

    if re.search(r"zinadan.*nafas|nafas qisiladi.*zinadan", normalized):
        _add("cardiology")

    if re.search(r"vazn yo['']?qot|kg yo['']?qot|ixtiyorsiz.*yo['']?qot", normalized):
        _add("oncology")

    if re.search(r"nafas qisish.*limfa|limfa tugun|tomoqchalar.*ko['']?z", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")
        _add("pulmonology")
        _add("ophthalmology")

    if re.search(r"ko['']?p dori|polypharmacy|uyqu tabletkasi.*yiqil", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")
        _add("neurology")

    if re.search(r"bo['']?g['']?im og['']?ri.*terlash|terlash.*bo['']?g['']?im", normalized):
        _add("rheumatology")

    if re.search(r"yashil balgam|surunkali yo['']?tal", normalized):
        _add("infectious_diseases")

    if re.search(r"qandli diabet.*yara|diabet.*oyoq.*yara", normalized):
        _add("neurology")

    if re.search(r"og['']?riqsiz qon|painless.*hematur", normalized):
        _add("oncology")

    if re.search(r"psoriaz.*bo['']?g['']?im|bo['']?g['']?im.*psoriaz", normalized):
        _add("rheumatology")

    if re.search(r"diqqat muammosi|ADHD|maktabda diqqat", normalized):
        _add("psychiatry")

    if re.search(r"o['']?lim qo['']?rqu|panika|o['']?lim", normalized):
        _add("psychiatry")

    if re.search(r"isitma.*lab.*yorilib|kawasaki|ko['']?zlari qizarib.*lab", normalized):
        _add("cardiology")

    if re.search(r"chakkam og['']?ri.*ko['']?rmay|chaynashda og['']?riq", normalized):
        _add("rheumatology")

    if re.search(r"ko['']?z ko['']?rmay.*birdan|birdan.*ko['']?rmay", normalized):
        _add("neurology")

    if re.search(r"90/50|qon bosim past.*39|nafas 28", normalized):
        _add("infectious_diseases")

    if re.search(r"spirt ichmay|alkogol.*ichmay|tush ko['']?ryapman", normalized):
        _add("emergency_medicine")

    if primary == "psychiatry" and re.search(r"spirt|alkogol|tush ko['']?ryapman|titrayapti", normalized):
        _add("emergency_medicine")

    if re.search(r"bolam.*isitma|isitma.*40.*bolam|bolam.*nafas qis", normalized):
        if primary != "pediatrics":
            _add("pediatrics")
        _add("emergency_medicine")
        _add("pulmonology")

    if re.search(r"isitma.*39|39.*isitma|titroq.*nafas qis|nafas qis.*titroq", normalized):
        if primary != "internal_medicine" and not re.search(r"qo['']?l.*ishlamay|gap.*buzil|insult|bolam|bola|siydik", normalized):
            _add("internal_medicine")

    if primary == "urology" and re.search(r"isitma|39|fever|tomonda", normalized):
        _add("infectious_diseases")

    if primary == "endocrinology" and re.search(r"yurak tez|yurak urish.*tez", normalized):
        _add("cardiology")

    if primary == "endocrinology" and re.search(r"guvda|tireotoks|gipertireoz", normalized) and re.search(
        r"isitma|40|titroq|yurak.*tez", normalized
    ):
        _add("emergency_medicine")

    if primary == "gynecology" and re.search(r"birdan boshlandi|birdan.*qus|qusdim", normalized) and re.search(
        r"qorin past|o['']?tkir", normalized
    ):
        _add("emergency_medicine")
        _add("general_surgery")

    if re.search(r"pufakchalar|pemphigus|og['']?izda pufak", normalized):
        if primary != "dermatology":
            _add("dermatology")
        _add("emergency_medicine")

    if re.search(r"qizar", normalized) and re.search(r"isitma|fever|38|39", normalized):
        if primary == "dermatology":
            _add("emergency_medicine")
            _add("infectious_diseases")

    if re.search(r"bolam|bola", normalized) and re.search(r"tozma", normalized) and re.search(
        r"isitma|39|38|fever", normalized
    ):
        _add("emergency_medicine")
        _add("infectious_diseases")
        if primary != "dermatology":
            _add("dermatology")

    if re.search(r"tozma.*oqmaydi|oqmaydi.*tozma|binafsha.*dog", normalized) and re.search(
        r"isitma|39|38|fever", normalized
    ):
        _add("emergency_medicine")
        _add("infectious_diseases")

    if re.search(r"siydik.*chiqmay|siydik tut|hojatxonaga qiyin", normalized):
        _add("emergency_medicine")
        _add("urology")

    if re.search(r"insulin|terlab|titroq.*terlash", normalized) and re.search(r"insulin|ovqat yemadim", normalized):
        _add("emergency_medicine")

    if re.search(r"yo['']?tal.*qon|qizil qon|qon ko['']?rdim", normalized):
        _add("emergency_medicine")
        _add("oncology")

    if re.search(r"qizarish kengay|tarqal.*qizarish", normalized):
        if primary != "dermatology":
            _add("dermatology")
        _add("emergency_medicine")
        _add("infectious_diseases")

    if re.search(r"butun tana.*tozma|tozma.*isitma.*38", normalized):
        _add("emergency_medicine")

    if re.search(r"bolam.*(haftalik|oylik)|haftalik.*bolam|8 haftalik", normalized):
        _add("emergency_medicine")

    if re.search(r"nafas qisish.*limfa|limfa.*shish.*nafas|tomoqchalar.*ko['']?z", normalized):
        if primary != "internal_medicine":
            _add("internal_medicine")
        _add("pulmonology")
        _add("ophthalmology")

    if re.search(r"bolam.*(gapira olmay|qiynalyapti|nafas olishda qattiq)", normalized):
        _add("emergency_medicine")
        _add("pulmonology")

    if re.search(r"qon bosim juda past|septik shok|laktat", normalized):
        _add("emergency_medicine")
        if primary != "intensive_care":
            _add("intensive_care")

    if re.search(r"siydik kamay|oliguri|yuzim shishgan.*siydik", normalized):
        if primary == "nephrology":
            _add("emergency_medicine")
        elif primary == "internal_medicine":
            _add("nephrology")

    if re.search(r"ko['']?k dog['']?|petexi|purpura", normalized) and re.search(r"isitma|fever", normalized):
        _add("emergency_medicine")
        if primary != "hematology":
            _add("hematology")

    if primary == "obstetrics":
        _add("emergency_medicine")

    if primary == "intensive_care":
        _add("emergency_medicine")
        _add("infectious_diseases")

    if re.search(r"yiqil|bilak.*shish|barmoq.*uvyapti|rangi o['']?zgardi", normalized):
        _add("emergency_medicine")
        if primary != "orthopedics":
            _add("orthopedics")

    if re.search(r"yelka.*chiqib ketdi|chiqib ketdi", normalized):
        _add("emergency_medicine")

    if re.search(r"qo['']?l.*ishlamay|gap.*buzil|gapim buzildi", normalized):
        if primary != "neurology":
            _add("neurology")
        _add("emergency_medicine")

    # Prioritize emergency — allow 4 secondaries when emergency present
    if "emergency_medicine" in extras:
        return extras[:4]
    return extras[:3]


def _neurology_category_boost(text: str, scores: dict[MedicalSpecialty, int]) -> None:
    category = classify_complaint(text)
    if category != "other_neurological":
        scores["neurology"] = scores.get("neurology", 0) + 2


def _resolve_primary_with_overrides(
    text: str, sorted_scores: list[tuple[MedicalSpecialty, int]]
) -> MedicalSpecialty:
    """Apply primary specialty overrides for clinically clear patterns."""
    normalized = (text or "").strip().lower()
    primary, _ = sorted_scores[0]

    # Dermatology / ENT / psychiatry — early overrides
    if re.search(r"pufakchalar|pufak.*og['']?iz|pemphigus|butun tana.*pufak", normalized):
        return "dermatology"

    if re.search(r"ovozim|ovoz.*xira|xira ovoz|hoarse", normalized):
        return "ent"

    if re.search(r"o['']?z joniga|suicid|o['']?zini o['']?ldir|o['']?ldirmoqchi|o['']?zimni o['']?ldir", normalized):
        return "psychiatry"

    if re.search(r"uyqu kerak emas|ko['']?p gapiryapman|pul sarflayapman|maniya", normalized):
        return "psychiatry"

    if re.search(r"belda o['']?tir|belda o['']?tkir|bel.*o['']?tkir|tizza og['']?ri.*qusish|siydikda qon.*bel|bel.*siydikda qon", normalized):
        return "urology"

    # Stroke FAST — highest priority
    if re.search(r"qo['']?l.*ishlamay|gap.*buzil|gapim buzildi|nutq.*buzil", normalized):
        return "neurology"

    # GI bleed before vertigo symptoms
    if re.search(r"qorong['']?u axlat|qorong['']?u rangli|melena", normalized):
        return "gastroenterology"

    # Hypoglycemia before generic tremor/vertigo routing
    if re.search(r"insulin", normalized) and re.search(r"terlab|titroq|ovqat yemadim", normalized):
        return "endocrinology"

    if re.search(r"terlab|titroq", normalized) and re.search(r"ovqat yemadim|shakar tush", normalized):
        return "endocrinology"

    if re.search(r"ko['']?z qism.*tush|qayta yutish|qayta yutolmay|ptosis", normalized):
        return "neurology"

    if re.search(r"yuz qizar|yuzim qizar|paroksism.*yurak|qon bosim 200|200/110", normalized) and re.search(
        r"terlash|yurak tez|titroq", normalized
    ):
        return "endocrinology"

    if re.search(r"spirt ichmay|alkogol.*ichmay|ichmay qo['']?ydim.*titray|tush ko['']?ryapman", normalized):
        return "psychiatry"

    if re.search(r"bolam|farzand|bola|chaqaloq", normalized) and not re.search(
        r"homilador|hayz|pelvik|menopauz", normalized
    ):
        return "pediatrics"

    if re.search(r"siydik", normalized) and re.search(r"isitma|39|og['']?riq|tomonda", normalized):
        return "urology"

    if re.search(r"titroq.*nafas qis|nafas qis.*39|isitma.*39.*titroq", normalized) and not re.search(
        r"qo['']?l.*ishlamay|gap.*buzil|insult|birdan.*ko['']?z|ko['']?krak.*eng kuchli|bolam|bola|siydik", normalized
    ):
        return "internal_medicine"

    if re.search(r"steroid.*ichmadim|dori.*ichmadim.*qusish|qon bosim past.*qusish", normalized):
        return "endocrinology"

    if re.search(r"qon bosim.*90/50|90/50.*qon bosim|nafas 28|sovuq terlash.*39", normalized):
        return "emergency_medicine"

    # Spreading cellulitis / erysipelas — skin redness worsening, with or without fever
    if re.search(
        r"qizarish kengay|tarqal.*qizarish|qizarib.*kengay|kengayapti.*qizar|"
        r"qizar.*kuchay|kuchayapti.*qizar|qol.*qizar|qolim qizar|oyoq qizarib|qizarib.*issiq.*kengay",
        normalized,
    ):
        return "dermatology"

    # Trauma + fracture before neuropathy from uvyapti
    if re.search(r"yiqil|yiqildim", normalized) and re.search(r"bilak|barmoq|tizza|yelka", normalized):
        return "orthopedics"

    if re.search(r"yelka.*chiqib ketdi|chiqib ketdi", normalized):
        return "orthopedics"

    if re.search(r"avtohalokat|halokat|travma|jarohat|qon ketayapti|tabletka ichib|hushsiz|onam hushsiz", normalized):
        return "emergency_medicine"

    if re.search(r"shishgan.*issiq|issiq.*shish|bog['']?im.*shish", normalized):
        if re.search(r"qizarib|kengayapti|tarqal", normalized):
            return "dermatology"
        return "rheumatology"

    if re.search(r"yiqil.*tush|bilak og['']?ri|tizza og['']?ri|yelka og['']?ri|bel og['']?ri", normalized):
        if "neurology" in dict(sorted_scores) and re.search(r"bel og['']?ri.*oyoq|siydik tut|hojatxonaga", normalized):
            return "neurology"
        return "orthopedics"

    if re.search(r"surunkali yo['']?tal|hushtak|astma", normalized):
        return "pulmonology"

    if re.search(r"hush.*ket|syncope|birdan hush", normalized):
        return "cardiology"

    if re.search(r"kuydirish|reflyuks|ovqatdan keyin.*kuydirish", normalized):
        return "gastroenterology"

    if re.search(r"charchoq.*sovuqqina|sovuqqina.*vazn ort", normalized):
        return "endocrinology"

    if re.search(r"vazn yo['']?qot.*titroq|titroq.*vazn yo['']?qot|yurak tez uradi.*vazn", normalized):
        return "endocrinology"

    if re.search(r"shakar tush|giperglikem", normalized):
        return "endocrinology"

    if re.search(r"qorin past", normalized):
        return "gynecology"

    if re.search(r"tugma.*rang|tugma.*shakl", normalized):
        return "dermatology"

    if re.search(r"qizarish.*issiq|tarqal.*qizarish", normalized):
        return "dermatology"

    if re.search(r"diabet|qandli diabet", normalized) and re.search(r"uvyapti|uvish", normalized):
        if re.search(r"qo['']?lim.*oyoq|oyoq.*qo['']?lim|qo['']?lim va oyoq", normalized):
            return "endocrinology"
        return "neurology"

    if re.search(r"diabet|qandli diabet|shakar tush|giperglik", normalized):
        return "endocrinology"

    if re.search(r"xotira yomon|xulq o['']?zgar", normalized) and re.search(r"isitma|fever|38", normalized):
        return "psychiatry"

    if re.search(r"o['']?z joniga|suicid|o['']?zini o['']?ldir|o['']?ldirmoqchi|o['']?zimni o['']?ldir", normalized):
        return "psychiatry"

    if re.search(r"ovozim|ovoz.*xira|xira ovoz|hoarse", normalized):
        return "ent"

    if re.search(r"pufakchalar|pufak.*og['']?iz|pemphigus", normalized):
        return "dermatology"

    if re.search(r"guvda|tsh|gipotireoz|gipertireoz|tireotoks", normalized) and re.search(r"isitma|40|titroq", normalized):
        return "endocrinology"

    if re.search(r"pufakchalar|pemphigus|og['']?izda pufak", normalized):
        return "dermatology"

    if re.search(r"anemiya|qon kam|holsiz.*hayz|hayz.*ko['']?p qon", normalized):
        return "internal_medicine"

    if re.search(r"ovozim|ovoz.*xira|xira ovoz|hoarse", normalized):
        return "ent"

    if re.search(r"ko['']?p ichaman.*ko['']?p siyaman|ko['']?p siyaman.*ko['']?p ichaman", normalized):
        return "endocrinology"

    if re.search(r"oyoq.*kuchsiz.*yuqoridan|kuchsiz.*tarqalmoqda|ascending", normalized):
        return "neurology"

    if re.search(r"moyak og['']?ri|testis|testikul", normalized):
        return "urology"

    if re.search(r"quloq eshitmay|eshitish.*yo['']?qol|birdan.*eshitish", normalized):
        return "ent"

    if re.search(r"ko['']?z.*ko['']?rmay|ko['']?rish.*pasay|parda tush|chaqnash", normalized):
        return "ophthalmology"

    if re.search(r"ovozlar eshit|kuzatilayotgandek|halusinat", normalized):
        return "psychiatry"

    if re.search(r"sababsiz.*isitma|isitma.*topilmadi|tungi terlash.*safar", normalized):
        return "internal_medicine"

    if re.search(r"pulsatsiya|yorug['']?likdan|migren|chakkamda", normalized):
        return "neurology"

    if re.search(r"eng kuchli og['']?riq|hayotimdagi eng kuchli|birdan juda qattiq.*bosh", normalized):
        return "neurology"

    if re.search(r"yuz.*qiysh|qiyshay", normalized):
        return "neurology"

    if re.search(r"menopauz", normalized):
        return "gynecology"

    if re.search(r"zinadan.*nafas|nafas qisiladi.*shish|oyoqlarim shishadi", normalized):
        return "cardiology"

    if re.search(r"doimiy bosh aylan|vertigo.*yurish qiyin", normalized):
        return "neurology"

    if re.search(r"homilador|hayz|pelvik|akint", normalized):
        return "gynecology"

    if re.search(r"psoriaz", normalized):
        return "dermatology"

    # Multi-system sarcoidosis pattern — IM primary
    if re.search(r"tomoqchalar", normalized) and re.search(r"nafas|ko['']?z qizar", normalized):
        return "internal_medicine"

    # Nephrology
    if re.search(r"siydik kamay|oliguri|anuri|ko['']?pikli siydik|nefrot", normalized):
        return "nephrology"
    if re.search(r"belda og['']?ri.*siydik|siydik.*belda|pielonefrit", normalized):
        return "nephrology"

    # Rheumatology
    if re.search(r"bo['']?g['']?im.*ertalab qattiq|ertalab qattiq.*bo['']?g['']?im", normalized):
        return "rheumatology"
    if re.search(r"bosh barmoq og['']?ri|podagra|kristal artrit", normalized):
        return "rheumatology"
    if re.search(r"quyoshdan keyin yomonlash|lupus|sle", normalized):
        return "rheumatology"

    # Hematology
    if re.search(r"ko['']?k dog['']?|ekimoz|petexi|purpura", normalized):
        return "hematology"
    if re.search(r"burun qoni|platelet|qon suyultir", normalized):
        return "hematology"

    # Obstetrics (pregnancy-specific; gynecology handles general pelvic)
    if re.search(r"homiladorman.*(?:bosh og['']?ri|ko['']?rish|qon bosim|qon ket|suv ket|qusish)", normalized):
        return "obstetrics"
    if re.search(r"homiladorman.*(?:nafas|harakat kamay|36w|34w|28w|10w)", normalized):
        return "obstetrics"

    # Intensive care / critical illness
    if re.search(r"qon bosim juda past|septik shok|shok.*hush", normalized):
        return "intensive_care"
    if re.search(r"kislorod yordam bermay|intubats|ventilyator|ICU", normalized):
        return "intensive_care"
    if re.search(r"ko['']?p organ yetish|multiorgan|laktat", normalized):
        return "intensive_care"

    # Oncology cues
    if re.search(r"ko['']?krakda qattiq to['']?p|limfa.*shish.*vazn", normalized):
        return "oncology"

    if re.search(r"tozma|terisi|qichish", normalized):
        return "dermatology"

    return primary


def route_medical_specialties(text: str) -> SpecialtyRouting:
    """Identify primary and secondary specialties for a patient message."""
    scores = _score_specialties(text)
    _apply_multi_specialty_hints(text, scores)
    _neurology_category_boost(text, scores)

    if not scores:
        scores = {"internal_medicine": 0}

    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    primary = _resolve_primary_with_overrides(text, sorted_scores)
    top_score = dict(sorted_scores).get(primary, sorted_scores[0][1])

    secondary: list[MedicalSpecialty] = []
    threshold = max(1, top_score // 2)
    for specialty, score in sorted_scores[1:]:
        if score >= threshold and specialty != primary:
            secondary.append(specialty)

    secondary = _apply_coordination_rules(text, primary, secondary)

    normalized = (text or "").lower()
    is_emergency = bool(
        primary == "emergency_medicine"
        or "emergency_medicine" in secondary
        or (primary == "cardiology" and re.search(r"ko['']?krak|chest|hush.*ket", normalized))
        or (primary == "neurology" and re.search(
            r"kuchsiz|nutq.*buzil|insult|stroke|tutqanoq|hush.*ket|eng kuchli bosh|birdan juda|"
            r"qo['']?l.*ishlamay|gap.*buzil",
            normalized,
        ))
        or (primary == "general_surgery")
        or re.search(
            r"avtohalokat|halokat|qon ketayapti|hushsiz|tabletka ichib|nafas qis.*ko['']?krak|"
            r"homiladorman.*qon|siydik tut|hojatxonaga qiyin|qon chiqyapti|qorong['']?u axlat|"
            r"insulin.*terlab|qizarish kengay|8 haftalik|chiqib ketdi|o['']?ng pastga|"
            r"qizil qon|yiqildim.*bilak|gapira olmay|tutqanoq|eshitmay|ko['']?rmay|"
            r"o['']?z joniga|tabletka ichib|birdan.*ko['']?z|quloq eshitmay",
            normalized,
        )
    )
    confidence = "high" if top_score >= 4 else "medium" if top_score >= 2 else "low"

    labels = [primary, *secondary]
    reasoning = f"Pattern scores suggest: {', '.join(labels)} (top score {top_score})."

    return SpecialtyRouting(
        primary=primary,
        secondary=secondary[:4],
        scores=dict(scores),
        confidence=confidence,
        is_emergency=is_emergency,
        reasoning=reasoning,
    )


def is_medical_consultation_trigger(text: str) -> bool:
    """True if message should route to Medical Brain consultation."""
    routing = route_medical_specialties(text)
    if routing.primary != "internal_medicine" or routing.scores:
        return True
    normalized = (text or "").strip().lower()
    medical_hints = (
        "og'ri", "ogri", "og‘ri", "pain", "hurt", "ache", "shikoyat",
        "symptom", "kasal", "doctor", "shifokor", "tibbiy",
    )
    return any(h in normalized for h in medical_hints)
