"""Disease-specific reasoning profiles — differential, investigations, treatment, referral."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiagnosisProfile:
    name: str
    prior_pct: float
    must_not_miss: bool = False


@dataclass(frozen=True)
class EvidenceRule:
    """When fact matches, multiply diagnosis likelihood."""

    topic_pattern: str
    value_pattern: str
    boosts: dict[str, float]  # diagnosis name -> multiplier
    suppresses: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SyndromeReasoningProfile:
    pathway_id: str
    diagnoses: tuple[DiagnosisProfile, ...]
    evidence_rules: tuple[EvidenceRule, ...]
    investigations: dict[str, tuple[str, ...]]  # diagnosis -> tests
    treatment: dict[str, tuple[str, ...]]  # diagnosis -> general approach
    referral: dict[str, str]  # diagnosis -> when to refer urgently
    mandatory_phases: tuple[str, ...] = ("triage", "discriminator")


_PROFILES: dict[str, SyndromeReasoningProfile] = {}


def _register(profile: SyndromeReasoningProfile) -> None:
    _PROFILES[profile.pathway_id] = profile


def get_reasoning_profile(pathway_id: str) -> SyndromeReasoningProfile | None:
    return _PROFILES.get(pathway_id)


def _bootstrap() -> None:
    _register(
        SyndromeReasoningProfile(
            pathway_id="lumbar_radiculopathy",
            diagnoses=(
                DiagnosisProfile("Lumbosakral radikulopatiya (disk herniyasi)", 42.0),
                DiagnosisProfile("Lumbal spinal stenoz", 18.0),
                DiagnosisProfile("Kas-iskelet bel og'rig'i", 15.0),
                DiagnosisProfile("Cauda equina sindromi", 8.0, must_not_miss=True),
                DiagnosisProfile("Vertebral infeksiya / malignansiya", 6.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule(
                    "radiation",
                    r"oyoq|boldir|tovon|tarqal",
                    {"Lumbosakral radikulopatiya (disk herniyasi)": 1.45, "Kas-iskelet bel og'rig'i": 0.7},
                ),
                EvidenceRule(
                    "neuro_deficit|deficit",
                    r"kuchsiz|uyuq|sezgi|refleks",
                    {"Lumbosakral radikulopatiya (disk herniyasi)": 1.35, "Lumbal spinal stenoz": 1.2},
                ),
                EvidenceRule(
                    "cauda",
                    r"positive|ikki|siydik|najas|hojat",
                    {"Cauda equina sindromi": 2.5, "Lumbosakral radikulopatiya (disk herniyasi)": 0.5},
                ),
                EvidenceRule(
                    "cauda",
                    r"negative|yo'q",
                    {"Cauda equina sindromi": 0.3, "Lumbosakral radikulopatiya (disk herniyasi)": 1.1},
                ),
                EvidenceRule(
                    "onset",
                    r"sudden|birdan",
                    {"Lumbosakral radikulopatiya (disk herniyasi)": 1.25},
                ),
                EvidenceRule(
                    "red_flag",
                    r"isitma|vazn|travma|saraton|positive",
                    {"Vertebral infeksiya / malignansiya": 1.8, "Kas-iskelet bel og'rig'i": 0.6},
                ),
                EvidenceRule(
                    "aggravating",
                    r"o'tir|yur|yoqish",
                    {"Lumbal spinal stenoz": 1.3, "Lumbosakral radikulopatiya (disk herniyasi)": 1.15},
                ),
            ),
            investigations={
                "Lumbosakral radikulopatiya (disk herniyasi)": (
                    "Nevrologik ko'rik",
                    "Lumbal MRI (4–6 haftadan keyin davom etsa yoki defitsit bo'lsa)",
                ),
                "Cauda equina sindromi": ("Zudlik bilan MRI", "Siydik tahlili"),
                "Vertebral infeksiya / malignansiya": ("Qon tahlili", "MRI", "Rentgen"),
            },
            treatment={
                "Lumbosakral radikulopatiya (disk herniyasi)": (
                    "Faol harakat cheklash, ergonomik o'zgarishlar",
                    "Fizioterapiya ko'rsatmalari",
                    "Og'riq qoldiruvchi faqat shifokor tavsiyasi bilan",
                ),
                "Lumbal spinal stenoz": (
                    "Yurish masofasini bosqichma-bosqich oshirish",
                    "Egilganda yengillashadigan pozalar",
                ),
                "Cauda equina sindromi": ("Shoshilinch jarrohlik/nevrologik baholash — kechiktirmang",),
            },
            referral={
                "Cauda equina sindromi": "Darhol shoshilinch yordam va jarroh/nevrolog",
                "Vertebral infeksiya / malignansiya": "Zudlik bilan shifokor ko'rigi",
                "Lumbosakral radikulopatiya (disk herniyasi)": "6 haftadan oshsa yoki kuchsizlik kuchaysa nevrolog",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="lumbar_spine",
            diagnoses=(
                DiagnosisProfile("Kas-iskelet bel og'rig'i", 45.0),
                DiagnosisProfile("Lumbal spinal stenoz", 22.0),
                DiagnosisProfile("Lumbosakral radikulopatiya", 18.0),
                DiagnosisProfile("Cauda equina sindromi", 5.0, must_not_miss=True),
                DiagnosisProfile("Vertebral patologiya (infeksiya/malignansiya)", 5.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("radiation", r"oyoq|chanoq|tarqal", {"Lumbosakral radikulopatiya": 1.5}),
                EvidenceRule("cauda", r"positive|ikki|siydik", {"Cauda equina sindromi": 2.2}),
                EvidenceRule("location", r"bir\s*tomon", {"Lumbosakral radikulopatiya": 1.2}),
                EvidenceRule("function", r"yurish|o'tirish|qiyin", {"Lumbal spinal stenoz": 1.3}),
            ),
            investigations={
                "Kas-iskelet bel og'rig'i": ("Klinik ko'rik",),
                "Lumbosakral radikulopatiya": ("MRI", "Nevrologik ko'rik"),
            },
            treatment={
                "Kas-iskelet bel og'rig'i": ("Faol harakat, bel mushaklarini mustahkamlash", "Issiq kompress"),
            },
            referral={
                "Cauda equina sindromi": "Darhol shoshilinch yordam",
                "Vertebral patologiya (infeksiya/malignansiya)": "Zudlik bilan baholash",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="headache",
            diagnoses=(
                DiagnosisProfile("Migren", 35.0),
                DiagnosisProfile("Tension-type bosh og'rig'i", 28.0),
                DiagnosisProfile("Klaster bosh og'rig'i", 12.0),
                DiagnosisProfile("Subarachnoid qon ketish (SAH)", 8.0, must_not_miss=True),
                DiagnosisProfile("Ikkinchi darajali bosh og'rig'i", 10.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("snoop", r"positive|birdan|kuchsiz|nutq|isitma", {"Subarachnoid qon ketish (SAH)": 2.0, "Ikkinchi darajali bosh og'rig'i": 1.6}),
                EvidenceRule("snoop", r"negative", {"Subarachnoid qon ketish (SAH)": 0.4, "Migren": 1.1}),
                EvidenceRule("character", r"pulsatsiya|chakka|bir\s*tomon", {"Migren": 1.5, "Klaster bosh og'rig'i": 1.3}),
                EvidenceRule("character", r"siqish|ikki\s*tomon|lenta", {"Tension-type bosh og'rig'i": 1.5}),
                EvidenceRule("associated", r"ko'ngil|yorug'|sezgir|chaqmoq", {"Migren": 1.6}),
                EvidenceRule("onset", r"sudden|birdan", {"Subarachnoid qon ketish (SAH)": 1.8}),
            ),
            investigations={
                "Subarachnoid qon ketish (SAH)": ("Zudlik bilan KT/MRT", "Lumbal punksiya"),
                "Migren": ("Klinik ko'rik", "Kundalik yuritish"),
                "Ikkinchi darajali bosh og'rig'i": ("MRT/KT", "Qon tahlili"),
            },
            treatment={
                "Migren": ("Triggerlardan qochish", "Tinch muhit", "Rejalashtirilgan davolash shifokor bilan"),
                "Tension-type bosh og'rig'i": ("Stress boshqaruvi", "Bo'yin mushaklarini cho'zish"),
            },
            referral={
                "Subarachnoid qon ketish (SAH)": "Darhol 103 / shoshilinch yordam",
                "Ikkinchi darajali bosh og'rig'i": "Zudlik bilan nevrolog/nevrokhirurg",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="peripheral_neuropathy",
            diagnoses=(
                DiagnosisProfile("Diabetik neuropatiya", 35.0),
                DiagnosisProfile("Idiopatik / nutritional neuropatiya", 25.0),
                DiagnosisProfile("Radikulopatiya (orqa fon)", 15.0),
                DiagnosisProfile("Guillain-Barré sindromi", 8.0, must_not_miss=True),
                DiagnosisProfile("Spinal patologiya", 10.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("progression", r"tez|birdan|bir\s*tomon", {"Guillain-Barré sindromi": 2.0, "Spinal patologiya": 1.5}),
                EvidenceRule("associated", r"diabet|qand|b12|alkogol|dori", {"Diabetik neuropatiya": 1.6}),
                EvidenceRule("distribution", r"qo'l|oyoq|barmoq|kaft|symmetr", {"Diabetik neuropatiya": 1.3, "Idiopatik / nutritional neuropatiya": 1.2}),
                EvidenceRule("motor", r"kuchsiz|positive", {"Guillain-Barré sindromi": 1.5, "Radikulopatiya (orqa fon)": 1.3}),
            ),
            investigations={
                "Diabetik neuropatiya": ("Qandni nazorat", "Elektronevrologiya (EMG/ENG)"),
                "Guillain-Barré sindromi": ("Zudlik bilan EMG", "BOS tahlili"),
            },
            treatment={
                "Diabetik neuropatiya": ("Qandni nazorat qilish", "Oyoq parvarishi"),
                "Idiopatik / nutritional neuropatiya": ("B12/vitamin tekshiruvi", "Sababni aniqlash"),
            },
            referral={
                "Guillain-Barré sindromi": "Darhol shoshilinch yordam",
                "Spinal patologiya": "Zudlik bilan MRI va nevrolog",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="cervical_radiculopathy",
            diagnoses=(
                DiagnosisProfile("Servikal radikulopatiya", 50.0),
                DiagnosisProfile("Servikal miyelopatiya", 15.0, must_not_miss=True),
                DiagnosisProfile("Karpal tunnel / periferik nerv", 20.0),
                DiagnosisProfile("Insult (fokal defitsit)", 8.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("myelo", r"positive|ikki|yurish|kuchsiz", {"Servikal miyelopatiya": 2.2, "Insult (fokal defitsit)": 1.5}),
                EvidenceRule("distribution", r"barmoq|kaft|C6|C7|C8", {"Servikal radikulopatiya": 1.4}),
                EvidenceRule("motor", r"kuchsiz|tush", {"Servikal radikulopatiya": 1.3}),
            ),
            investigations={
                "Servikal radikulopatiya": ("Servikal MRI", "Nevrologik ko'rik"),
                "Servikal miyelopatiya": ("Zudlik bilan MRI", "Jarroh/nevrolog"),
            },
            treatment={
                "Servikal radikulopatiya": ("Bo'yin ergonomikasi", "Fizioterapiya"),
            },
            referral={
                "Servikal miyelopatiya": "Zudlik bilan jarroh/nevrolog",
                "Insult (fokal defitsit)": "Darhol 103",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="migraine",
            diagnoses=(
                DiagnosisProfile("Migren", 55.0),
                DiagnosisProfile("Tension-type bosh og'rig'i", 25.0),
                DiagnosisProfile("Klaster bosh og'rig'i", 12.0),
                DiagnosisProfile("Ikkinchi darajali bosh og'rig'i", 5.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("snoop", r"negative", {"Migren": 1.15}),
                EvidenceRule("character", r"pulsatsiya|chakka", {"Migren": 1.5}),
                EvidenceRule("associated", r"ko'ngil|yorug'|chaqmoq", {"Migren": 1.6}),
            ),
            investigations={"Migren": ("Klinik ko'rik",)},
            treatment={"Migren": ("Triggerlardan qochish", "Rejalashtirilgan profilaktika shifokor bilan")},
            referral={"Ikkinchi darajali bosh og'rig'i": "Yangi/progressiv bosh og'rig'ida zudlik bilan baholash"},
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="stroke_acute",
            diagnoses=(
                DiagnosisProfile("Ishemik insult", 55.0),
                DiagnosisProfile("Gemorragik insult", 25.0, must_not_miss=True),
                DiagnosisProfile("TIA", 15.0),
            ),
            evidence_rules=(
                EvidenceRule("deficit", r"yuz|qo'l|oyoq|nutq", {"Ishemik insult": 1.3, "Gemorragik insult": 1.2}),
                EvidenceRule("progression", r"kuchay|yomonlash", {"Gemorragik insult": 1.5}),
            ),
            investigations={
                "Ishemik insult": ("Zudlik bilan KT/MRT", "Qon tahlili"),
                "Gemorragik insult": ("Zudlik bilan KT",),
            },
            treatment={
                "Ishemik insult": ("Vaqt muhim — shoshilinch stantsionar yordam",),
                "Gemorragik insult": ("Shoshilinch KT va neyrokhirurgik baho",),
            },
            referral={
                "Ishemik insult": "Darhol 103 — tromboliz vaqt oynasi",
                "Gemorragik insult": "Darhol 103",
            },
        )
    )


_bootstrap()
