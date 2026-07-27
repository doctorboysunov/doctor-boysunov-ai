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

    _register(
        SyndromeReasoningProfile(
            pathway_id="cervical_spine",
            diagnoses=(
                DiagnosisProfile("Mexanik/miofastial bo'yin og'rig'i", 45.0),
                DiagnosisProfile("Servikal radikulopatiya", 22.0),
                DiagnosisProfile("Servikal miyelopatiya", 10.0, must_not_miss=True),
                DiagnosisProfile("Meningit / vaskulyar disseksiya", 8.0, must_not_miss=True),
                DiagnosisProfile("Boshqa sabab (tension bosh og'rig'i bilan qo'shilgan)", 15.0),
            ),
            evidence_rules=(
                EvidenceRule("myelo", r"positive|kuchsiz|yurish", {"Servikal miyelopatiya": 2.0, "Mexanik/miofastial bo'yin og'rig'i": 0.6}),
                EvidenceRule("myelo", r"negative", {"Servikal miyelopatiya": 0.35}),
                EvidenceRule("radiation", r"qo'l|barmoq", {"Servikal radikulopatiya": 1.45, "Mexanik/miofastial bo'yin og'rig'i": 0.7}),
                EvidenceRule("red_flags", r"positive|isitma|nutq|ko'rish|travma", {"Meningit / vaskulyar disseksiya": 2.0, "Mexanik/miofastial bo'yin og'rig'i": 0.5}),
                EvidenceRule("aggravating", r"positive|harakat|burish", {"Mexanik/miofastial bo'yin og'rig'i": 1.3}),
            ),
            investigations={
                "Servikal radikulopatiya": ("Servikal MRI", "Nevrologik ko'rik"),
                "Servikal miyelopatiya": ("Zudlik bilan MRI", "Jarroh/nevrolog"),
                "Meningit / vaskulyar disseksiya": ("Zudlik bilan KT/angiografiya", "Shifoxonaga yotqizish"),
            },
            treatment={
                "Mexanik/miofastial bo'yin og'rig'i": ("Bo'yin ergonomikasi", "Faol harakat, issiq kompress"),
                "Servikal radikulopatiya": ("Fizioterapiya ko'rsatmalari",),
            },
            referral={
                "Servikal miyelopatiya": "Zudlik bilan jarroh/nevrolog",
                "Meningit / vaskulyar disseksiya": "Darhol 103",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="vestibular",
            diagnoses=(
                DiagnosisProfile("Xosh sifatli pozitsion vertigo (BPPV)", 38.0),
                DiagnosisProfile("Vestibulyar nevrit / labirintit", 22.0),
                DiagnosisProfile("Meniere kasalligi", 12.0),
                DiagnosisProfile("Markaziy vertigo (insult/TIA)", 10.0, must_not_miss=True),
                DiagnosisProfile("Boshqa sabab", 18.0),
            ),
            evidence_rules=(
                EvidenceRule("central_screen", r"positive|nutq|kuchsiz|koordinatsiya", {"Markaziy vertigo (insult/TIA)": 2.2, "Xosh sifatli pozitsion vertigo (BPPV)": 0.5}),
                EvidenceRule("central_screen", r"negative", {"Markaziy vertigo (insult/TIA)": 0.35}),
                EvidenceRule("timing", r"soniya|qisqa", {"Xosh sifatli pozitsion vertigo (BPPV)": 1.6}),
                EvidenceRule("timing", r"soat|kun|uzoq", {"Vestibulyar nevrit / labirintit": 1.4, "Meniere kasalligi": 1.2}),
                EvidenceRule("position", r"positive|burish|yotish", {"Xosh sifatli pozitsion vertigo (BPPV)": 1.5}),
                EvidenceRule("hearing", r"eshitish|shov|tortish", {"Meniere kasalligi": 1.7}),
                EvidenceRule("associated", r"qusish|ko'ngil", {"Vestibulyar nevrit / labirintit": 1.2}),
            ),
            investigations={
                "Xosh sifatli pozitsion vertigo (BPPV)": ("Dix-Hallpike testi",),
                "Markaziy vertigo (insult/TIA)": ("Zudlik bilan MRI/KT", "Nevrolog ko'rigi"),
                "Meniere kasalligi": ("Audiometriya", "LOR ko'rigi"),
            },
            treatment={
                "Xosh sifatli pozitsion vertigo (BPPV)": ("Epley manevri (shifokor tomonidan)",),
                "Vestibulyar nevrit / labirintit": ("Simptomatik davo", "Vestibulyar reabilitatsiya"),
            },
            referral={
                "Markaziy vertigo (insult/TIA)": "Darhol 103",
                "Meniere kasalligi": "Rejalashtirilgan LOR/nevrolog ko'rigi",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="facial_nerve",
            diagnoses=(
                DiagnosisProfile("Bell falaji", 52.0),
                DiagnosisProfile("Ramsay Hunt sindromi", 14.0),
                DiagnosisProfile("Sentral fasial falaj (insult)", 14.0, must_not_miss=True),
                DiagnosisProfile("Otit/mastoidit bilan bog'liq falaj", 8.0),
                DiagnosisProfile("Boshqa sabab", 12.0),
            ),
            evidence_rules=(
                EvidenceRule("central_screen", r"positive|qo'l|oyoq|nutq", {"Sentral fasial falaj (insult)": 2.2, "Bell falaji": 0.55}),
                EvidenceRule("central_screen", r"negative", {"Sentral fasial falaj (insult)": 0.3}),
                EvidenceRule("complete", r"to'liq|peshona", {"Bell falaji": 1.5, "Sentral fasial falaj (insult)": 0.4}),
                EvidenceRule("complete", r"pastki|faqat.*lab", {"Sentral fasial falaj (insult)": 1.6}),
                EvidenceRule("ear", r"quloq|toshma|tovush", {"Ramsay Hunt sindromi": 1.9, "Bell falaji": 0.7}),
            ),
            investigations={
                "Sentral fasial falaj (insult)": ("Zudlik bilan KT/MRT",),
                "Ramsay Hunt sindromi": ("LOR ko'rigi", "Antiviral davo baholash"),
                "Bell falaji": ("Nevrologik ko'rik",),
            },
            treatment={
                "Bell falaji": ("Erta kortikosteroid (shifokor tavsiyasi)", "Ko'z parvarishi"),
                "Ramsay Hunt sindromi": ("Antiviral + kortikosteroid — shifokor tavsiyasi",),
            },
            referral={
                "Sentral fasial falaj (insult)": "Darhol 103",
                "Ramsay Hunt sindromi": "Zudlik bilan shifokor ko'rigi",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="bell_palsy",
            diagnoses=(
                DiagnosisProfile("Bell falaji", 58.0),
                DiagnosisProfile("Ramsay Hunt sindromi", 16.0),
                DiagnosisProfile("Sentral fasial falaj (insult)", 13.0, must_not_miss=True),
                DiagnosisProfile("Boshqa sabab", 13.0),
            ),
            evidence_rules=(
                EvidenceRule("central_screen", r"positive|qo'l|oyoq|nutq", {"Sentral fasial falaj (insult)": 2.2, "Bell falaji": 0.55}),
                EvidenceRule("central_screen", r"negative", {"Sentral fasial falaj (insult)": 0.3}),
                EvidenceRule("completeness", r"to'liq|peshona", {"Bell falaji": 1.5}),
                EvidenceRule("completeness", r"pastki|faqat.*lab", {"Sentral fasial falaj (insult)": 1.6}),
                EvidenceRule("ear_symptoms", r"quloq|toshma|tovush", {"Ramsay Hunt sindromi": 1.9, "Bell falaji": 0.7}),
            ),
            investigations={
                "Sentral fasial falaj (insult)": ("Zudlik bilan KT/MRT",),
                "Bell falaji": ("Nevrologik ko'rik",),
            },
            treatment={
                "Bell falaji": ("Erta kortikosteroid (shifokor tavsiyasi)", "Ko'z parvarishi"),
                "Ramsay Hunt sindromi": ("Antiviral + kortikosteroid — shifokor tavsiyasi",),
            },
            referral={
                "Sentral fasial falaj (insult)": "Darhol 103",
                "Ramsay Hunt sindromi": "Zudlik bilan shifokor ko'rigi",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="parkinsonian",
            diagnoses=(
                DiagnosisProfile("Parkinson kasalligi (idiopatik)", 38.0),
                DiagnosisProfile("Essensial tremor", 24.0),
                DiagnosisProfile("Dori-induksiyalangan parkinsonizm", 16.0),
                DiagnosisProfile("Atipik parkinsonizm (MSA/PSP)", 10.0, must_not_miss=True),
                DiagnosisProfile("Boshqa sabab", 12.0),
            ),
            evidence_rules=(
                EvidenceRule("red_flags", r"positive|yiqil|nutq|yutish|tez", {"Atipik parkinsonizm (MSA/PSP)": 2.0, "Parkinson kasalligi (idiopatik)": 0.6}),
                EvidenceRule("rest_action", r"dam ol", {"Parkinson kasalligi (idiopatik)": 1.5, "Essensial tremor": 0.6}),
                EvidenceRule("rest_action", r"harakat|reaching|yozganda", {"Essensial tremor": 1.6, "Parkinson kasalligi (idiopatik)": 0.6}),
                EvidenceRule("associated", r"sekinlash|yuz ifoda|yurish", {"Parkinson kasalligi (idiopatik)": 1.5}),
                EvidenceRule("meds", r"metoklopramid|antipsixotik|dori", {"Dori-induksiyalangan parkinsonizm": 2.0, "Parkinson kasalligi (idiopatik)": 0.5}),
                EvidenceRule("meds", r"negative|yo'q", {"Dori-induksiyalangan parkinsonizm": 0.4}),
            ),
            investigations={
                "Parkinson kasalligi (idiopatik)": ("Nevrolog ko'rigi", "Levodopa sinov davosi"),
                "Atipik parkinsonizm (MSA/PSP)": ("MRI", "Zudlik nevrolog ko'rigi"),
            },
            treatment={
                "Essensial tremor": ("Kofein/stress cheklash", "Shifokor bilan dorilarni ko'rib chiqish"),
                "Dori-induksiyalangan parkinsonizm": ("Sababchi dorini shifokor bilan qayta ko'rib chiqish",),
            },
            referral={
                "Atipik parkinsonizm (MSA/PSP)": "Zudlik bilan nevrolog ko'rigi",
                "Parkinson kasalligi (idiopatik)": "Rejalashtirilgan nevrolog ko'rigi",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="epilepsy",
            diagnoses=(
                DiagnosisProfile("Ma'lum epilepsiya (nazorat buzilishi)", 30.0),
                DiagnosisProfile("Birinchi provokatsiyalanmagan tutqanoq", 22.0),
                DiagnosisProfile("Provokatsiyalangan tutqanoq (isitma/alkogol/metabolik)", 18.0),
                DiagnosisProfile("Status epileptikus / aktiv hujum", 15.0, must_not_miss=True),
                DiagnosisProfile("Sinkopa / psixogen noeleptik hujum", 15.0),
            ),
            evidence_rules=(
                EvidenceRule("active_seizure", r"positive|davom|hushsiz", {"Status epileptikus / aktiv hujum": 2.5, "Sinkopa / psixogen noeleptik hujum": 0.5}),
                EvidenceRule("active_seizure", r"negative", {"Status epileptikus / aktiv hujum": 0.25}),
                EvidenceRule("first_ever", r"birinchi", {"Birinchi provokatsiyalanmagan tutqanoq": 1.6}),
                EvidenceRule("first_ever", r"oldin.*bo'l|takror", {"Ma'lum epilepsiya (nazorat buzilishi)": 1.6}),
                EvidenceRule("triggers", r"alkogol|uyqusiz|stress|isitma", {"Provokatsiyalangan tutqanoq (isitma/alkogol/metabolik)": 1.8}),
                EvidenceRule("duration", r"5\s*daqiqa|uzoq|to'xtamay", {"Status epileptikus / aktiv hujum": 1.8}),
                EvidenceRule("semiology", r"hush yo'qol|qotish|qo'l.*oyoq", {"Ma'lum epilepsiya (nazorat buzilishi)": 1.2, "Sinkopa / psixogen noeleptik hujum": 0.7}),
            ),
            investigations={
                "Status epileptikus / aktiv hujum": ("Zudlik shoshilinch yordam", "EEG"),
                "Birinchi provokatsiyalanmagan tutqanoq": ("EEG", "MRI"),
                "Provokatsiyalangan tutqanoq (isitma/alkogol/metabolik)": ("Qon tahlili", "Metabolik skrining"),
            },
            treatment={
                "Ma'lum epilepsiya (nazorat buzilishi)": ("Dori qabul qilish rejimini nevrolog bilan qayta ko'rib chiqish",),
            },
            referral={
                "Status epileptikus / aktiv hujum": "Darhol 103",
                "Birinchi provokatsiyalanmagan tutqanoq": "Zudlik bilan nevrolog ko'rigi",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="memory_cognitive",
            diagnoses=(
                DiagnosisProfile("Yengil kognitiv buzilish (MCI)", 32.0),
                DiagnosisProfile("Alzheimer tipidagi demensiya", 24.0),
                DiagnosisProfile("Vaskulyar demensiya", 16.0),
                DiagnosisProfile("Depressiya bilan bog'liq psevdodemensiya", 16.0),
                DiagnosisProfile("Zudlik talab qiluvchi sabab (NPH/o'sma/metabolik)", 12.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("red_flags", r"positive|tez|bosh og'ri|nutq|yurish", {"Zudlik talab qiluvchi sabab (NPH/o'sma/metabolik)": 2.2, "Yengil kognitiv buzilish (MCI)": 0.5}),
                EvidenceRule("red_flags", r"negative", {"Zudlik talab qiluvchi sabab (NPH/o'sma/metabolik)": 0.35}),
                EvidenceRule("function", r"pul|dori|yo'l|qiyinlash", {"Alzheimer tipidagi demensiya": 1.5, "Vaskulyar demensiya": 1.3, "Yengil kognitiv buzilish (MCI)": 0.6}),
                EvidenceRule("onset", r"asta|sekin", {"Alzheimer tipidagi demensiya": 1.4}),
                EvidenceRule("onset", r"birdan|bosqichma|step", {"Vaskulyar demensiya": 1.6}),
            ),
            investigations={
                "Zudlik talab qiluvchi sabab (NPH/o'sma/metabolik)": ("Zudlik bilan MRI", "Qon tahlili (B12, TSH)"),
                "Alzheimer tipidagi demensiya": ("Kognitiv test (MMSE/MoCA)", "MRI"),
            },
            treatment={
                "Depressiya bilan bog'liq psevdodemensiya": ("Ruhiy holatni baholash — psixiatr/nevrolog",),
            },
            referral={
                "Zudlik talab qiluvchi sabab (NPH/o'sma/metabolik)": "Zudlik bilan nevrolog/MRI",
                "Alzheimer tipidagi demensiya": "Rejalashtirilgan nevrolog/kognitiv klinika",
            },
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="unclassified_neurology",
            diagnoses=(
                DiagnosisProfile("Klinik suratga qarab aniqlanadi", 60.0),
                DiagnosisProfile("Zudlik talab qiluvchi nevrologik sabab", 40.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("red_flags", r"positive|nutq|ko'rish|birdan.*kuchsiz|kuchsiz.*birdan|bosh og'ri", {"Zudlik talab qiluvchi nevrologik sabab": 2.2, "Klinik suratga qarab aniqlanadi": 0.6}),
                EvidenceRule("red_flags", r"negative", {"Zudlik talab qiluvchi nevrologik sabab": 0.4}),
                EvidenceRule("associated", r"tarqal|kuchay", {"Zudlik talab qiluvchi nevrologik sabab": 1.3}),
                EvidenceRule("duration", r"oy|yil|surunkali|uzoq", {"Klinik suratga qarab aniqlanadi": 1.2, "Zudlik talab qiluvchi nevrologik sabab": 0.7}),
            ),
            investigations={"Zudlik talab qiluvchi nevrologik sabab": ("Zudlik nevrolog ko'rigi",)},
            treatment={},
            referral={"Zudlik talab qiluvchi nevrologik sabab": "Zudlik bilan nevrolog ko'rigi"},
        )
    )

    _register(
        SyndromeReasoningProfile(
            pathway_id="general_neurology",
            diagnoses=(
                DiagnosisProfile("Klinik suratga qarab aniqlanadi", 60.0),
                DiagnosisProfile("Zudlik talab qiluvchi nevrologik sabab", 40.0, must_not_miss=True),
            ),
            evidence_rules=(
                EvidenceRule("red_flags", r"positive|nutq|ko'rish|hush|birdan.*kuchsiz|kuchsiz.*birdan|bosh og'ri", {"Zudlik talab qiluvchi nevrologik sabab": 2.2, "Klinik suratga qarab aniqlanadi": 0.6}),
                EvidenceRule("red_flags", r"negative", {"Zudlik talab qiluvchi nevrologik sabab": 0.4}),
                EvidenceRule("associated", r"tarqal|kuchay", {"Zudlik talab qiluvchi nevrologik sabab": 1.3}),
                EvidenceRule("duration", r"oy|yil|surunkali|uzoq", {"Klinik suratga qarab aniqlanadi": 1.2, "Zudlik talab qiluvchi nevrologik sabab": 0.7}),
            ),
            investigations={"Zudlik talab qiluvchi nevrologik sabab": ("Zudlik nevrolog ko'rigi",)},
            treatment={},
            referral={"Zudlik talab qiluvchi nevrologik sabab": "Zudlik bilan nevrolog ko'rigi"},
        )
    )


_bootstrap()
