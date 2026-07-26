"""100 doctor-level clinical challenge case templates — 14 specialties."""

from __future__ import annotations

from app.medical_brain.evaluation.clinical_challenge.types import ChallengeCase, ConversationTurn

SPECIALTY_ORDER = (
    "neurology",
    "cardiology",
    "internal_medicine",
    "pulmonology",
    "gastroenterology",
    "endocrinology",
    "urology",
    "gynecology",
    "dermatology",
    "pediatrics",
    "ent",
    "ophthalmology",
    "psychiatry",
    "emergency_medicine",
)


def _turns(*pairs: tuple[str, str], flags: dict[int, tuple[bool, bool]] | None = None) -> list[ConversationTurn]:
    """Build turns from (role, content) pairs. flags maps index -> (interruption, misinformation)."""
    flags = flags or {}
    out: list[ConversationTurn] = []
    for i, (role, content) in enumerate(pairs):
        intr, mis = flags.get(i, (False, False))
        out.append(ConversationTurn(role=role, content=content, is_interruption=intr, contains_misinformation=mis))
    return out


def _case(
    case_id: str,
    title: str,
    specialty: str,
    category: str,
    profile: str,
    turns: list[ConversationTurn],
    primary: str,
    *,
    secondary: list[str] | None = None,
    red_flags: list[str] | None = None,
    differentials: list[str] | None = None,
    emergency: bool = False,
    hidden: str = "",
    misinfo: str = "",
    reasoning: str = "",
    forbidden: list[str] | None = None,
    referral: str = "",
    hint: str = "",
) -> ChallengeCase:
    return ChallengeCase(
        id=case_id,
        title=title,
        specialty=specialty,
        category=category,
        patient_profile=profile,
        turns=turns,
        expected_primary=primary,
        expected_secondary=secondary or [],
        expected_red_flags=red_flags or [],
        expected_differentials=differentials or [],
        requires_emergency=emergency,
        hidden_red_flag=hidden,
        patient_misinformation=misinfo,
        expected_reasoning=reasoning,
        forbidden_questions=forbidden or [],
        expected_referral=referral,
        improvement_hint=hint,
    )


# --- Neurology (7) ---
_NEUROLOGY = [
    _case(
        "dc_001", "Stroke with patient minimization", "neurology", "emergency",
        "Male, 68y, hypertensive",
        _turns(
            ("user", "Qo'lim biroz og'riyapti, lekin o'tib ketadi deb o'ylayman"),
            ("assistant", "Qachondan boshlangan?"),
            ("user", "Kecha kechqurun. Yo'q, aslida bugun ertalab — qo'lim ishlamayapti, gapim buzildi!"),
            flags={2: (True, False)},
        ),
        "neurology", secondary=["emergency_medicine"], red_flags=["stroke", "focal deficit"],
        differentials=["stroke", "TIA"], emergency=True, hidden="FAST symptoms revealed after correction",
        hint="Document last known well; do not accept initial minimization",
    ),
    _case(
        "dc_002", "Thunderclap headache — hidden SAH", "neurology", "hidden_red_flag",
        "Female, 45y",
        _turns(
            ("user", "Bosh og'rig'i bor, stressdan deb o'ylayman"),
            ("assistant", "Qanday boshlandi?"),
            ("user", "Birdan, eng kuchli og'riq — hayotimdagi eng yomon. Bo'yin qattiq."),
        ),
        "neurology", secondary=["emergency_medicine"], red_flags=["thunderclap"],
        differentials=["SAH", "meningitis"], emergency=True, hidden="thunderclap + neck stiffness",
        hint="Triage thunderclap before location questions",
    ),
    _case(
        "dc_003", "Cauda equina — multi-complaint", "neurology", "multi_complaint",
        "Male, 55y, back pain history",
        _turns(
            ("user", "Bel og'riyapti, oyoqlarim ham og'riyapti"),
            ("assistant", "Siydik yoki axlat boshqarishda muammo bormi?"),
            ("user", "Ha, hojatxonaga qiyin, oyoqlarim uiydi. Og'riq 2 kun."),
        ),
        "neurology", secondary=["emergency_medicine", "urology"], red_flags=["cauda"],
        differentials=["cauda equina", "disc herniation"], emergency=True,
        hint="Bladder/bowel before chronicity",
    ),
    _case(
        "dc_004", "Migraine vs SAH — wrong attribution", "neurology", "misinformation",
        "Female, 32y",
        _turns(
            ("user", "Migrenim bor deb o'ylayman, chakkamda pulsatsiya"),
            ("assistant", "Bu safar oldingi migrenlardan farqi bormi?"),
            ("user", "Ha, bu safar birdan boshlandi va juda kuchli. Ko'ngil aynish bor."),
            flags={2: (False, True)},
        ),
        "neurology", secondary=["emergency_medicine"], red_flags=["thunderclap"],
        differentials=["migraine", "SAH"], emergency=True,
        misinfo="Patient self-diagnoses migraine",
        hint="New severe headache pattern overrides prior migraine label",
    ),
    _case(
        "dc_005", "Guillain-Barré — rare ascending weakness", "neurology", "rare",
        "Male, 28y, recent URI",
        _turns(
            ("user", "Oyoqlarim kuchsiz, yuqoridan pastga tarqalmoqda"),
            ("assistant", "Nafas olishda qiyinchilik bormi?"),
            ("user", "Ha, nafas olishda qiyinchilik bor. 5 kun oldin shamollagan edim."),
        ),
        "neurology", secondary=["emergency_medicine"], red_flags=["breathing"],
        differentials=["Guillain-Barré", "myelopathy"], emergency=True,
        hint="Ascending weakness + respiratory symptoms = urgent neuro",
    ),
    _case(
        "dc_006", "Chronic migraine follow-up", "neurology", "chronic_followup",
        "Female, 40y, known migraine",
        _turns(
            ("user", "Migrenim yomonlashdi, oyiga 12 marta"),
            ("assistant", "Dori yordam beradimi?"),
            ("user", "Sumatriptan yordam bermayapti. Ishdan qolmoqdaman."),
        ),
        "neurology", differentials=["chronic migraine", "medication overuse"],
        reasoning="Assess frequency, triggers, preventive therapy",
        hint="Chronic migraine — preventives not just acute meds",
    ),
    _case(
        "dc_007", "BPPV — common vertigo", "neurology", "common",
        "Female, 60y",
        _turns(
            ("user", "Bosh aylanishi, faqat yotib turganimda"),
            ("assistant", "Har bir epizod qancha davom etadi?"),
            ("user", "30 soniya, keyin o'tadi. Qusish yo'q."),
        ),
        "neurology", differentials=["BPPV", "central vertigo"],
        reasoning="Positional, brief episodes — peripheral pattern",
        hint="Duration and position trigger before central workup",
    ),
]

# --- Cardiology (7) ---
_CARDIOLOGY = [
    _case(
        "dc_008", "ACS with denial", "cardiology", "emergency",
        "Male, 58y, smoker",
        _turns(
            ("user", "Ko'kragim biroz og'riyapti, nafas olishda"),
            ("assistant", "Og'riq qayerga tarqaladi?"),
            ("user", "Chap qo'liga, 40 daqiqadan beri. Terlab qoldim."),
            flags={2: (True, False)},
        ),
        "cardiology", secondary=["emergency_medicine"], red_flags=["chest_pain"],
        differentials=["ACS", "PE"], emergency=True,
        hint="Radiation + diaphoresis = ACS pathway",
    ),
    _case(
        "dc_009", "Heart failure decompensation", "cardiology", "chronic_followup",
        "Female, 72y, known HF",
        _turns(
            ("user", "Yurak yetishmovchiligi bor, hozir nafas qisilyapti"),
            ("assistant", "Tungi nafas qisish yoki oyoq shishi bormi?"),
            ("user", "Ha, kechasi 2 marta uyg'onaman, oyoqlarim shishgan."),
        ),
        "cardiology", secondary=["emergency_medicine"], differentials=["HF decompensation", "pneumonia"],
        emergency=True, hint="Orthopnea/PND/edema triad",
    ),
    _case(
        "dc_010", "Aortic dissection — rare emergency", "cardiology", "rare",
        "Male, 65y, hypertensive",
        _turns(
            ("user", "Ko'krak og'rig'i birdan boshlandi, orqaga tarqaladi"),
            ("assistant", "Og'riq qanday — yirtib ketayotgandekmi?"),
            ("user", "Ha, yirtib ketayotgandek. Chap va o'ng qo'l bosimlari farq qiladi deb ayishyapti."),
        ),
        "cardiology", secondary=["emergency_medicine"], red_flags=["chest_pain"],
        differentials=["aortic dissection", "ACS"], emergency=True,
        hint="Tearing pain + pulse deficit = dissection",
    ),
    _case(
        "dc_011", "Palpitations — common", "cardiology", "common",
        "Female, 35y",
        _turns(
            ("user", "Yurak urishim tezlashyapti"),
            ("assistant", "Qachondan va qancha davom etadi?"),
            ("user", "1 soat, hushim ketmadi. Kofe ichgan edim."),
        ),
        "cardiology", differentials=["SVT", "anxiety"],
        reasoning="Duration, hemodynamic symptoms, triggers",
    ),
    _case(
        "dc_012", "Syncope during exertion", "cardiology", "emergency",
        "Male, 22y, athlete",
        _turns(
            ("user", "Sport paytida hushim ketdi"),
            ("assistant", "Oldin ham bo'lganmi?"),
            ("user", "Yo'q, birinchi marta. Hushim 2 daqiqada qaytdi."),
        ),
        "cardiology", secondary=["emergency_medicine", "neurology"], differentials=["HOCM", "arrhythmia"],
        emergency=True, hint="Exertional syncope = cardiac red flag",
    ),
    _case(
        "dc_013", "Multi-complaint chest + reflux", "cardiology", "multi_complaint",
        "Male, 50y",
        _turns(
            ("user", "Ko'kragimda kuydirish bor, ovqatdan keyin. Ba'zan og'riq ham."),
            ("assistant", "Og'riq nafas olishda kuchayadimi?"),
            ("user", "Ha, zinadan chiqqanda ham nafas qisiladi."),
        ),
        "gastroenterology", secondary=["cardiology"], differentials=["ACS", "GERD", "HF"],
        reasoning="Screen cardiac even with reflux pattern",
    ),
    _case(
        "dc_014", "Atrial fibrillation — chronic", "cardiology", "chronic_followup",
        "Male, 70y, on anticoagulation",
        _turns(
            ("user", "Yurak aritmiyam bor, bugun yurak urishi tartibsiz"),
            ("assistant", "Qon qoidalari qabul qilasizmi?"),
            ("user", "Ha, varfarin. Bosh og'rig'i yo'q, hushim joyida."),
        ),
        "cardiology", differentials=["AF with RVR", "bleed"],
        reasoning="Rate control, anticoagulation, stroke symptoms",
    ),
]

# --- Internal Medicine (7) ---
_INTERNAL = [
    _case(
        "dc_015", "Fever of unknown origin", "internal_medicine", "common",
        "Male, 45y",
        _turns(
            ("user", "2 haftadan beri isitmam bor, sababi topilmadi"),
            ("assistant", "Safar qilganmisiz yoki hayvon bilan aloqa bormi?"),
            ("user", "Ha, 1 oy oldin Hindistonga bordim. Tungi terlash ham bor."),
        ),
        "internal_medicine", secondary=["infectious_diseases"],
        red_flags=[], differentials=["malaria", "TB", "lymphoma"],
        hint="Travel history + night sweats = broad workup",
    ),
    _case(
        "dc_016", "Unexplained weight loss — malignancy screen", "internal_medicine", "hidden_red_flag",
        "Female, 62y",
        _turns(
            ("user", "Charchoq va holsizlik, hech narsa qilolmayapman"),
            ("assistant", "Vazn o'zgarish bormi?"),
            ("user", "8 kg yo'qotdim 3 oyda, ixtiyorsiz. Ishtaham yo'q."),
        ),
        "internal_medicine", secondary=["oncology"], red_flags=["weight_loss"],
        differentials=["malignancy", "hyperthyroidism", "depression"],
        hidden="8kg unintentional weight loss",
        hint="Constitutional symptoms before attributing to stress",
    ),
    _case(
        "dc_017", "Sarcoidosis — rare multi-system", "internal_medicine", "rare",
        "Female, 35y",
        _turns(
            ("user", "Nafas qisish, terida tomoqchalar, ko'z qizarishi"),
            ("assistant", "Qaysi organlar shikoyat qilyapti?"),
            ("user", "Ikkala tomondan limfa tugunlari ham shishgan."),
        ),
        "internal_medicine", secondary=["pulmonology", "ophthalmology"],
        differentials=["sarcoidosis", "TB", "lymphoma"],
        hint="Multi-system — lungs, skin, eyes, lymph nodes",
    ),
    _case(
        "dc_018", "Polypharmacy elderly", "internal_medicine", "chronic_followup",
        "Male, 80y, 8 medications",
        _turns(
            ("user", "Ko'p dori ichaman, bosh aylanishi va yiqilish xavfi"),
            ("assistant", "Qaysi dorilar?"),
            ("user", "Qon bosim, yurak, uyqu tabletkalari. Kecha yiqilib tushdim."),
        ),
        "internal_medicine", secondary=["neurology"],
        differentials=["orthostatic hypotension", "polypharmacy"],
        hint="Medication review before new prescriptions",
    ),
    _case(
        "dc_019", "Multi-complaint fatigue + pain", "internal_medicine", "multi_complaint",
        "Female, 48y",
        _turns(
            ("user", "Charchoq, bo'g'im og'rig'i, terlash"),
            ("assistant", "Isitma bormi?"),
            ("user", "Kechqurun 37.8. Qo'llarim ertalab qattiq."),
        ),
        "internal_medicine", secondary=["rheumatology"],
        differentials=["RA", "fibromyalgia", "hypothyroidism"],
    ),
    _case(
        "dc_020", "Patient wrong timeline", "internal_medicine", "misinformation",
        "Male, 55y",
        _turns(
            ("user", "1 haftadan beri isitmam bor deb o'ylayman"),
            ("assistant", "Boshqa simptomlar?"),
            ("user", "Aslida 3 kun — 39.5, titroq, nafas qisish bor."),
            flags={2: (False, True)},
        ),
        "internal_medicine", secondary=["infectious_diseases", "emergency_medicine"],
        differentials=["sepsis", "pneumonia"], emergency=True,
        misinfo="Patient underestimates severity/duration",
    ),
    _case(
        "dc_021", "Anemia workup", "internal_medicine", "common",
        "Female, 30y",
        _turns(
            ("user", "Tez charchayman, ko'z oldim qorayadi"),
            ("assistant", "Hayz ko'rish qanday?"),
            ("user", "Ko'p va ko'p qon ketadi, 7 kun."),
        ),
        "internal_medicine", secondary=["gynecology"],
        differentials=["iron deficiency", "menorrhagia"],
    ),
]

# --- Pulmonology (7) ---
_PULMONOLOGY = [
    _case(
        "dc_022", "PE with travel history", "pulmonology", "emergency",
        "Female, 35y, on OCP",
        _turns(
            ("user", "Nafas olish qiyin, ko'krak og'rig'i"),
            ("assistant", "Safar qilganmisiz?"),
            ("user", "Ha, 12 soatlik parvoz. Oyoq shishgan edi."),
        ),
        "pulmonology", secondary=["emergency_medicine", "cardiology"],
        differentials=["PE", "ACS"], emergency=True,
        hint="Wells criteria elements — travel, OCP, unilateral leg swelling",
    ),
    _case(
        "dc_023", "COPD exacerbation", "pulmonology", "chronic_followup",
        "Male, 68y, COPD",
        _turns(
            ("user", "Surunkali yo'talim yomonlashdi, yashil balgam"),
            ("assistant", "Nafas qisish qanchalik?"),
            ("user", "Hatto gapirganda ham. 3 kun oldin boshlandi."),
        ),
        "pulmonology", secondary=["infectious_diseases"],
        differentials=["COPD exacerbation", "pneumonia"],
    ),
    _case(
        "dc_024", "Hemoptysis + weight loss", "pulmonology", "emergency",
        "Male, 62y, smoker",
        _turns(
            ("user", "Yo'tal paytida qon chiqyapti"),
            ("assistant", "Vazn o'zgarish yoki isitma?"),
            ("user", "5 kg yo'qotdim, 40 yil chekaman."),
        ),
        "pulmonology", secondary=["oncology", "emergency_medicine"],
        red_flags=["hemoptysis", "weight_loss"],
        differentials=["lung cancer", "TB", "bronchiectasis"], emergency=True,
    ),
    _case(
        "dc_025", "Asthma attack", "pulmonology", "common",
        "Female, 25y, asthmatic",
        _turns(
            ("user", "Nafas qisilyapti, hushtak chiqyapti"),
            ("assistant", "Inhaler ishlatdingizmi?"),
            ("user", "Ha, yordam bermadi. Gapirish qiyin."),
        ),
        "pulmonology", secondary=["emergency_medicine"],
        differentials=["asthma exacerbation"], emergency=True,
    ),
    _case(
        "dc_026", "Pneumothorax — rare spontaneous", "pulmonology", "rare",
        "Male, 20y, tall thin",
        _turns(
            ("user", "Birdan ko'krak og'rig'i va nafas qisish"),
            ("assistant", "Oldin shunday bo'lganmi?"),
            ("user", "Yo'q. O'ng tomonda o'tkir og'riq."),
        ),
        "pulmonology", secondary=["emergency_medicine"],
        differentials=["pneumothorax", "PE"], emergency=True,
    ),
    _case(
        "dc_027", "Interruption — anxiety vs asthma", "pulmonology", "interruption",
        "Female, 30y",
        _turns(
            ("user", "Nafas olish qiyin —"),
            ("assistant", "Qachondan?"),
            ("user", "— kechadan beri! Hushtak ham bor, uyquda uyg'onaman!"),
            flags={2: (True, False)},
        ),
        "pulmonology", secondary=["emergency_medicine"],
        differentials=["asthma", "panic"], emergency=True,
    ),
    _case(
        "dc_028", "Chronic cough workup", "pulmonology", "common",
        "Male, 55y, non-smoker",
        _turns(
            ("user", "3 haftadan beri yo'talim bor"),
            ("assistant", "Qon yoki isitma bormi?"),
            ("user", "Yo'q qon, isitma ham yo'q. ACE inhibitor ichaman."),
        ),
        "pulmonology", differentials=["ACE cough", "post-infectious", "GERD"],
    ),
]

# --- Gastroenterology (7) ---
_GASTRO = [
    _case(
        "dc_029", "Upper GI bleed", "gastroenterology", "emergency",
        "Male, 50y, NSAID use",
        _turns(
            ("user", "Qorong'u axlat, bosh aylanishi"),
            ("assistant", "Qorin og'rig'i yoki qusish?"),
            ("user", "Qorin og'rig'i bor, 2 marta qusdim — qora."),
        ),
        "gastroenterology", secondary=["emergency_medicine"],
        red_flags=["melena", "bleeding"], differentials=["GI bleed", "peptic ulcer"],
        emergency=True,
    ),
    _case(
        "dc_030", "Appendicitis migration", "gastroenterology", "common",
        "Male, 22y",
        _turns(
            ("user", "Qorin og'riyapti, ko'ngil aynish"),
            ("assistant", "Og'riq qayerdan boshlangan?"),
            ("user", "Avval qorin markazida, endi o'ng pastga ko'chdi."),
        ),
        "gastroenterology", secondary=["general_surgery", "emergency_medicine"],
        differentials=["appendicitis", "gastroenteritis"], emergency=True,
    ),
    _case(
        "dc_031", "Pancreatitis", "gastroenterology", "emergency",
        "Male, 45y, alcoholic",
        _turns(
            ("user", "Qorin yuqori qismida og'riq, belga tarqaladi"),
            ("assistant", "Qusish yoki isitma?"),
            ("user", "Ha, qusdim 3 marta. 39 isitma."),
        ),
        "gastroenterology", secondary=["emergency_medicine"],
        differentials=["pancreatitis", "cholecystitis"], emergency=True,
    ),
    _case(
        "dc_032", "IBD flare — chronic", "gastroenterology", "chronic_followup",
        "Female, 28y, Crohn's",
        _turns(
            ("user", "Crohn kasalligim bor, qorin og'rig'i yomonlashdi"),
            ("assistant", "Axlat qanday — qon bormi?"),
            ("user", "Suyuq, qon aralash. 8 marta bugun."),
        ),
        "gastroenterology", secondary=["emergency_medicine"],
        differentials=["IBD flare", "infection"], emergency=True,
    ),
    _case(
        "dc_033", "GERD vs cardiac — misinformation", "gastroenterology", "misinformation",
        "Male, 55y",
        _turns(
            ("user", "Reflyuksim bor, ko'krak kuydirishi — odatiy"),
            ("assistant", "Bu safar farqi bormi?"),
            ("user", "Ha, nafas olishda kuchayadi va chap qo'liga tarqaladi."),
            flags={2: (False, True)},
        ),
        "gastroenterology", secondary=["cardiology", "emergency_medicine"],
        differentials=["ACS", "GERD"], emergency=True,
        misinfo="Patient attributes cardiac symptoms to reflux",
    ),
    _case(
        "dc_034", "Wilson disease — rare", "gastroenterology", "rare",
        "Male, 22y",
        _turns(
            ("user", "Qorin shishgan, sariq ko'z, titroq"),
            ("assistant", "Oilalarizda jigar kasalligi bormi?"),
            ("user", "Akam ham yoshda jigar muammosi bo'lgan."),
        ),
        "gastroenterology", secondary=["neurology"],
        differentials=["Wilson disease", "hepatitis", "cirrhosis"],
    ),
    _case(
        "dc_035", "Multi-complaint abd + back", "gastroenterology", "multi_complaint",
        "Female, 40y",
        _turns(
            ("user", "Qorin og'rig'i va bel og'rig'i"),
            ("assistant", "Hayz sikli qanday?"),
            ("user", "Kechikdi, homiladorlik testi qilmoqchiman."),
        ),
        "gastroenterology", secondary=["gynecology"],
        differentials=["ectopic", "ovarian cyst", "appendicitis"],
    ),
]

# --- Endocrinology (7) ---
_ENDO = [
    _case(
        "dc_036", "DKA presentation", "endocrinology", "emergency",
        "Male, 18y, new diabetes",
        _turns(
            ("user", "Ko'p ichaman, ko'p siyaman, qusish"),
            ("assistant", "Nafas hidini eshitdingizmi — meva hid?"),
            ("user", "Ha, nafasim g'alati hidli. Hushim biroz lox."),
        ),
        "endocrinology", secondary=["emergency_medicine"],
        red_flags=["dka"],
        differentials=["DKA", "HHS"], emergency=True,
    ),
    _case(
        "dc_037", "Hypoglycemia on insulin", "endocrinology", "emergency",
        "Female, 65y, diabetic",
        _turns(
            ("user", "Terlab, titroq, bosh aylanishi"),
            ("assistant", "Insulin qachon olgansiz?"),
            ("user", "Bugun ertalab, ovqat yemadim."),
        ),
        "endocrinology", secondary=["emergency_medicine"],
        red_flags=["hypoglycemia"], differentials=["hypoglycemia"], emergency=True,
    ),
    _case(
        "dc_038", "Thyroid storm — rare", "endocrinology", "rare",
        "Female, 35y, hyperthyroid",
        _turns(
            ("user", "Yurak juda tez, isitma 40, titroq"),
            ("assistant", "Guvdagi kasallik bormi?"),
            ("user", "Ha, guvda kasalligim bor, dori ichmay qo'ydim."),
        ),
        "endocrinology", secondary=["emergency_medicine", "cardiology"],
        differentials=["thyroid storm", "infection"], emergency=True,
    ),
    _case(
        "dc_039", "Diabetes follow-up", "endocrinology", "chronic_followup",
        "Male, 50y, T2DM",
        _turns(
            ("user", "Qandli diabetim bor, shakarim yuqori"),
            ("assistant", "Oyoqlarda uyuq yoki yaralar bormi?"),
            ("user", "Oyoq barmog'imda yara bor, 2 haftadan beri bitmayapti."),
        ),
        "endocrinology", secondary=["neurology"],
        differentials=["diabetic foot", "neuropathy"],
    ),
    _case(
        "dc_040", "Hypothyroid — common", "endocrinology", "common",
        "Female, 45y",
        _turns(
            ("user", "Charchoq, sovuqqina, vazn ortyapti"),
            ("assistant", "Teri quruq yoki soch to'kilishi?"),
            ("user", "Ha, ikkalasi ham. 6 oydan beri."),
        ),
        "endocrinology", differentials=["hypothyroidism", "depression"],
    ),
    _case(
        "dc_041", "Addison crisis — hidden", "endocrinology", "hidden_red_flag",
        "Female, 30y, on steroids",
        _turns(
            ("user", "Kuchli zaiflik, qorin og'rig'i"),
            ("assistant", "Steroid dori ishlatasizmi?"),
            ("user", "Ha, lekin 1 hafta ichmadim. Qon bosim past, qusish bor."),
        ),
        "endocrinology", secondary=["emergency_medicine"],
        differentials=["Addison crisis", "sepsis"], emergency=True,
        hidden="Steroid withdrawal + hypotension",
    ),
    _case(
        "dc_042", "Multi-complaint polyuria + vision", "endocrinology", "multi_complaint",
        "Male, 40y",
        _turns(
            ("user", "Ko'p siyaman va ko'rishim bulutli"),
            ("assistant", "Vazn o'zgarish?"),
            ("user", "5 kg yo'qotdim 1 oyda."),
        ),
        "endocrinology", secondary=["ophthalmology"],
        red_flags=["weight_loss"], differentials=["new diabetes", "hyperthyroidism"],
    ),
]

# --- Urology (7) ---
_UROLOGY = [
    _case(
        "dc_043", "Testicular torsion", "urology", "emergency",
        "Male, 16y",
        _turns(
            ("user", "Moyak og'riyapti, birdan boshlandi"),
            ("assistant", "Qachondan va qaysi tomonda?"),
            ("user", "2 soat oldin, o'ng tomonda. Qusish ham bor."),
        ),
        "urology", secondary=["emergency_medicine"],
        differentials=["torsion", "epididymitis"], emergency=True,
    ),
    _case(
        "dc_044", "Painless hematuria", "urology", "common",
        "Male, 58y, smoker",
        _turns(
            ("user", "Siydikda qon ko'rdim, og'riqsiz"),
            ("assistant", "Bir marta yoki takrorlanadimi?"),
            ("user", "3 marta bu hafta. Sigaret chekaman."),
        ),
        "urology", secondary=["oncology"],
        differentials=["bladder cancer", "UTI", "stone"],
    ),
    _case(
        "dc_045", "Pyelonephritis", "urology", "common",
        "Female, 35y",
        _turns(
            ("user", "Siydik qilishda og'riq, isitma"),
            ("assistant", "Bel og'rig'i bormi?"),
            ("user", "Ha, o'ng tomonda. 39.2 isitma."),
        ),
        "urology", secondary=["infectious_diseases"],
        differentials=["pyelonephritis", "UTI"],
    ),
    _case(
        "dc_046", "Acute retention", "urology", "emergency",
        "Male, 70y, BPH",
        _turns(
            ("user", "Siydik chiqmayapti, qorin shishgan"),
            ("assistant", "Qancha vaqt?"),
            ("user", "12 soat. Qorin juda og'riyapti."),
        ),
        "urology", secondary=["emergency_medicine"],
        differentials=["retention", "cauda equina"], emergency=True,
    ),
    _case(
        "dc_047", "Renal colic", "urology", "common",
        "Male, 40y",
        _turns(
            ("user", "Belda o'tkir og'riq, qusish"),
            ("assistant", "Siydikda qon bormi?"),
            ("user", "Ha, pushti rang. Og'riq to'lqinli."),
        ),
        "urology", differentials=["renal colic", "AAA"],
    ),
    _case(
        "dc_048", "Wrong self-diagnosis UTI", "urology", "misinformation",
        "Female, 50y",
        _turns(
            ("user", "Siydik yo'li infeksiyam bor deb o'ylayman"),
            ("assistant", "Qon yoki og'riqsiz qon bormi?"),
            ("user", "Ha, og'riqsiz qon. Antibiotik yordam bermadi."),
            flags={2: (False, True)},
        ),
        "urology", secondary=["oncology"],
        differentials=["bladder cancer", "UTI"],
        misinfo="Self-diagnosed UTI masking hematuria workup",
    ),
    _case(
        "dc_049", "Chronic prostatitis follow-up", "urology", "chronic_followup",
        "Male, 45y",
        _turns(
            ("user", "Prostatitim bor, qorin pastida og'riq davom etmoqda"),
            ("assistant", "Siydik oqimi qanday?"),
            ("user", "Zaif, kechasi 3 marta turaman."),
        ),
        "urology", differentials=["BPH", "prostatitis", "cancer"],
    ),
]

# --- Gynecology (7) ---
_GYNECO = [
    _case(
        "dc_050", "Ectopic pregnancy", "gynecology", "emergency",
        "Female, 28y",
        _turns(
            ("user", "Qorin pastida og'riq, homiladorlik testi ijobiy"),
            ("assistant", "Qon ketish bormi?"),
            ("user", "Biroz jigarrang ajratma. Chap tomonda o'tkir og'riq."),
        ),
        "gynecology", secondary=["emergency_medicine"],
        red_flags=["pregnancy bleeding"], differentials=["ectopic", "miscarriage"],
        emergency=True,
    ),
    _case(
        "dc_051", "Postmenopausal bleeding", "gynecology", "common",
        "Female, 58y",
        _turns(
            ("user", "Menopauzadan keyin qon ko'rdim"),
            ("assistant", "Qachondan va qanchalik?"),
            ("user", "2 haftadan beri, kam-kam. Og'riq yo'q."),
        ),
        "gynecology", secondary=["oncology"],
        differentials=["endometrial cancer", "polyps"],
    ),
    _case(
        "dc_052", "Ovarian torsion — rare", "gynecology", "rare",
        "Female, 25y",
        _turns(
            ("user", "Qorin pastida o'tkir og'riq, ko'ngil aynish"),
            ("assistant", "Homiladorlik ehtimoli?"),
            ("user", "Yo'q. Og'riq birdan boshlandi, qusdim."),
        ),
        "gynecology", secondary=["emergency_medicine", "general_surgery"],
        differentials=["torsion", "appendicitis", "ectopic"], emergency=True,
    ),
    _case(
        "dc_053", "PID", "gynecology", "common",
        "Female, 22y",
        _turns(
            ("user", "Qorin pastida og'riq, isitma, axlat hidli"),
            ("assistant", "Yangi jinsiy aloqa bormi?"),
            ("user", "Ha, himoya ishlatmadik."),
        ),
        "gynecology", secondary=["infectious_diseases"],
        differentials=["PID", "appendicitis", "ectopic"],
    ),
    _case(
        "dc_054", "Antepartum bleeding", "gynecology", "emergency",
        "Female, 32w pregnant",
        _turns(
            ("user", "Homiladorman, qon ketayapti"),
            ("assistant", "Qancha qon va og'riq bormi?"),
            ("user", "Ko'p qon, qattiq og'riq yo'q. Bebek harakat qilyapti."),
        ),
        "gynecology", secondary=["emergency_medicine"],
        red_flags=["pregnancy bleeding", "severe bleeding"], emergency=True,
    ),
    _case(
        "dc_055", "Interruption — pelvic pain", "gynecology", "interruption",
        "Female, 30y",
        _turns(
            ("user", "Qorin og'riyapti —"),
            ("assistant", "Qayerda?"),
            ("user", "— pastda! Hayz kechikdi, isitma 38!"),
            flags={2: (True, False)},
        ),
        "gynecology", secondary=["infectious_diseases"],
        differentials=["ectopic", "PID", "pregnancy"],
    ),
    _case(
        "dc_056", "Endometriosis chronic", "gynecology", "chronic_followup",
        "Female, 32y",
        _turns(
            ("user", "Hayz paytida juda og'riq, jinsiy aloqada ham og'riq"),
            ("assistant", "Homilador bo'lishga urinayapsizmi?"),
            ("user", "Ha, 2 yil muvaffaqiyatsiz. Og'riq kuchli."),
        ),
        "gynecology", differentials=["endometriosis", "adenomyosis"],
    ),
]

# --- Dermatology (7) ---
_DERMA = [
    _case(
        "dc_057", "Anaphylaxis", "dermatology", "emergency",
        "Female, 25y",
        _turns(
            ("user", "Tozma paydo bo'ldi, nafas olish qiyin"),
            ("assistant", "Nima yeyish yoki dori olgansiz?"),
            ("user", "Yong'oq yedim. Bo'g'ilib qolyapman!"),
        ),
        "dermatology", secondary=["emergency_medicine", "pulmonology"],
        red_flags=["breathing"], differentials=["anaphylaxis"], emergency=True,
    ),
    _case(
        "dc_058", "DRESS / drug rash", "dermatology", "emergency",
        "Male, 40y",
        _turns(
            ("user", "Butun tana tozma, isitma 38.5, ko'z qizarib"),
            ("assistant", "Yangi dori olganmisiz?"),
            ("user", "Ha, amoxicillin 1 hafta oldin boshladim."),
        ),
        "dermatology", secondary=["emergency_medicine"],
        red_flags=["drug rash"], differentials=["DRESS", "SJS"], emergency=True,
    ),
    _case(
        "dc_059", "Cellulitis spreading", "dermatology", "common",
        "Male, 55y",
        _turns(
            ("user", "Oyoq qizarib, issiq, kengayapti"),
            ("assistant", "Og'riq proporsionalmi — juda kuchlimi?"),
            ("user", "Ha, shishgan joydan kuchliroq og'riyapti."),
        ),
        "dermatology", secondary=["emergency_medicine", "infectious_diseases"],
        red_flags=["cellulitis"], differentials=["cellulitis", "necrotizing fasciitis"],
        emergency=True,
    ),
    _case(
        "dc_060", "Melanoma concern", "dermatology", "common",
        "Female, 50y",
        _turns(
            ("user", "Tugmacha rangi o'zgardi, kattalashyapti"),
            ("assistant", "Qachondan va qanday o'zgarish?"),
            ("user", "2 oy. Chegarasi notekis, qichish bor."),
        ),
        "dermatology", differentials=["melanoma", "dysplastic nevus"],
    ),
    _case(
        "dc_061", "Psoriasis chronic", "dermatology", "chronic_followup",
        "Male, 35y",
        _turns(
            ("user", "Psoriazim bor, yomonlashdi, bo'g'imlar ham og'riyapti"),
            ("assistant", "Qaysi bo'g'imlar?"),
            ("user", "Qo'l barmoqlari shishgan, ertalab qattiq."),
        ),
        "dermatology", secondary=["rheumatology"],
        differentials=["psoriatic arthritis", "RA"],
    ),
    _case(
        "dc_062", "Pemphigus — rare", "dermatology", "rare",
        "Male, 60y",
        _turns(
            ("user", "Og'izda pufakchalar, terida ham pufak"),
            ("assistant", "Pufaklar yoriladimi?"),
            ("user", "Ha, juda og'riqli. 2 haftadan beri."),
        ),
        "dermatology", secondary=["emergency_medicine"],
        differentials=["pemphigus", "bullous pemphigoid"],
    ),
    _case(
        "dc_063", "Hidden purpura fever", "dermatology", "hidden_red_flag",
        "Child proxy, 8y",
        _turns(
            ("user", "Bolamda tozma bor deb o'ylayman"),
            ("assistant", "Isitma bormi?"),
            ("user", "Ha, 39.5. Tozma bosilganda oqmaydi — binafsha dog'."),
        ),
        "pediatrics", secondary=["emergency_medicine", "infectious_diseases", "dermatology"],
        differentials=["meningococcemia", "vasculitis"], emergency=True,
        hidden="Non-blanching purpura + fever",
    ),
]

# --- Pediatrics (7) ---
_PEDIATRICS = [
    _case(
        "dc_064", "Infant fever", "pediatrics", "emergency",
        "Infant, 6 weeks",
        _turns(
            ("user", "Bolam 6 haftalik, isitmasi 38.5"),
            ("assistant", "Emizish qanday?"),
            ("user", "Kam emyapti, bezovta, yig'layapti."),
        ),
        "pediatrics", secondary=["emergency_medicine", "infectious_diseases"],
        red_flags=["infant fever"], differentials=["sepsis", "UTI", "meningitis"],
        emergency=True,
    ),
    _case(
        "dc_065", "Febrile seizure", "pediatrics", "common",
        "Child, 2y",
        _turns(
            ("user", "Bolam tutqanoq tutdi, isitmasi bor"),
            ("assistant", "Tutqanoq qancha davom etdi?"),
            ("user", "2 daqiqa. Hozir yaxshi. Isitma 39."),
        ),
        "pediatrics", secondary=["emergency_medicine", "neurology"],
        red_flags=["seizure"], differentials=["febrile seizure", "meningitis"],
    ),
    _case(
        "dc_066", "Pediatric respiratory distress", "pediatrics", "emergency",
        "Child, 3y",
        _turns(
            ("user", "Bolam nafas olishda qiynalyapti"),
            ("assistant", "Qo'ng'iz tortish yoki gapira oladimi?"),
            ("user", "Qo'ng'iz tortyapti, gapira olmayapti."),
        ),
        "pediatrics", secondary=["emergency_medicine", "pulmonology"],
        differentials=["croup", "asthma", "foreign body"], emergency=True,
    ),
    _case(
        "dc_067", "Dehydration", "pediatrics", "common",
        "Child, 1y",
        _turns(
            ("user", "Bolam qusyapti, ichmayapti"),
            ("assistant", "Siydik qancha?"),
            ("user", "Bugun 1 marta, odatda 6 marta. Lethargik."),
        ),
        "pediatrics", secondary=["emergency_medicine", "gastroenterology"],
        differentials=["dehydration", "pyloric stenosis"], emergency=True,
    ),
    _case(
        "dc_068", "Kawasaki — rare", "pediatrics", "rare",
        "Child, 4y",
        _turns(
            ("user", "Bolam 5 kundan beri isitma, ko'zlari qizarib, lablari yorilib"),
            ("assistant", "Terisi qanday?"),
            ("user", "Butun tana qizarib, qo'llari shishgan."),
        ),
        "pediatrics", secondary=["cardiology", "emergency_medicine"],
        differentials=["Kawasaki", "scarlet fever"], emergency=True,
    ),
    _case(
        "dc_069", "Parent misinformation", "pediatrics", "misinformation",
        "Child, 5y",
        _turns(
            ("user", "Bolam oddiy shamollash deb o'ylayman"),
            ("assistant", "Nafas olish qanday?"),
            ("user", "Aslida nafas qisish bor, ko'krak tortyapti, isitma 40."),
            flags={2: (False, True)},
        ),
        "pediatrics", secondary=["emergency_medicine", "pulmonology"],
        differentials=["pneumonia", "asthma"], emergency=True,
    ),
    _case(
        "dc_070", "ADHD follow-up", "pediatrics", "chronic_followup",
        "Child, 10y",
        _turns(
            ("user", "Farzandim maktabda diqqat muammosi, dori ichyapti"),
            ("assistant", "Yon ta'sirlar bormi?"),
            ("user", "Uyqu muammosi, ishtaha kamaygan."),
        ),
        "pediatrics", secondary=["psychiatry"],
        differentials=["ADHD", "sleep disorder"],
    ),
]

# --- ENT (7) ---
_ENT = [
    _case(
        "dc_071", "Sudden hearing loss", "ent", "emergency",
        "Male, 55y",
        _turns(
            ("user", "Birdan quloq eshitmay qoldi, o'ng tomonda"),
            ("assistant", "Og'riq yoki aylanish bormi?"),
            ("user", "Og'riq yo'q. Kecha kechqurun boshlandi."),
        ),
        "ent", secondary=["emergency_medicine"],
        differentials=["SSNHL", "cerumen impaction"], emergency=True,
    ),
    _case(
        "dc_072", "Peritonsillar abscess", "ent", "common",
        "Male, 20y",
        _turns(
            ("user", "Tomoq og'riyapti, yutish qiyin, og'iz ochish qiyin"),
            ("assistant", "Isitma va ovoz o'zgarish?"),
            ("user", "39 isitma, ovozim g'ijir. Bir tomonda shish bor."),
        ),
        "ent", secondary=["emergency_medicine", "infectious_diseases"],
        differentials=["quinsy", "pharyngitis"], emergency=True,
    ),
    _case(
        "dc_073", "Epiglottitis — rare", "ent", "rare",
        "Child, 6y",
        _turns(
            ("user", "Bolam yutolmayapti, nafas qisish, isitma"),
            ("assistant", "Tupurik oqadimi?"),
            ("user", "Ha, o'tirganda oldinga egiladi. 40 isitma."),
        ),
        "ent", secondary=["emergency_medicine", "pediatrics"],
        differentials=["epiglottitis", "croup"], emergency=True,
    ),
    _case(
        "dc_074", "Chronic sinusitis", "ent", "chronic_followup",
        "Female, 40y",
        _turns(
            ("user", "Burun tiqilib, bosh og'rig'i, 3 oydan beri"),
            ("assistant", "Ajratma qanday?"),
            ("user", "Yashil, ertalab ko'p. Allergiya bor."),
        ),
        "ent", differentials=["chronic sinusitis", "allergic rhinitis"],
    ),
    _case(
        "dc_075", "Vertigo overlap ENT-neuro", "ent", "multi_complaint",
        "Female, 50y",
        _turns(
            ("user", "Bosh aylanishi va quloq shovqini"),
            ("assistant", "Epizodlar qancha davom etadi?"),
            ("user", "4 soat, qusish bor. Eshitish pasaygan."),
        ),
        "ent", secondary=["neurology"],
        differentials=["Meniere", "vestibular neuritis", "central vertigo"],
    ),
    _case(
        "dc_076", "Foreign body — common", "ent", "common",
        "Child, 3y",
        _turns(
            ("user", "Bolam buruniga narsa solib qo'ygan"),
            ("assistant", "Nafas olishda muammo?"),
            ("user", "Yo'q, faqat bir tomonda burun tiqilib."),
        ),
        "ent", secondary=["pediatrics"],
        differentials=["foreign body", "rhinitis"],
    ),
    _case(
        "dc_077", "Hoarseness >3 weeks", "ent", "hidden_red_flag",
        "Male, 60y, smoker",
        _turns(
            ("user", "Ovozim o'zgardi, xira"),
            ("assistant", "Qachondan?"),
            ("user", "1 oydan beri. Sigaret 30 yil. Og'riq yo'q."),
        ),
        "ent", secondary=["oncology"],
        differentials=["laryngeal cancer", "reflux", "nodules"],
        hidden="Smoking + hoarseness >3 weeks",
    ),
]

# --- Ophthalmology (7) ---
_OPHTHAL = [
    _case(
        "dc_078", "Acute angle closure glaucoma", "ophthalmology", "emergency",
        "Female, 65y",
        _turns(
            ("user", "Ko'z og'riyapti, ko'rish bulutli, ko'ngil aynish"),
            ("assistant", "Qachondan va bir tomondami?"),
            ("user", "Bugun ertalab. O'ng ko'z. Halqa ko'raman."),
        ),
        "ophthalmology", secondary=["emergency_medicine"],
        differentials=["acute glaucoma", "migraine"], emergency=True,
    ),
    _case(
        "dc_079", "Retinal detachment", "ophthalmology", "emergency",
        "Male, 50y, myopic",
        _turns(
            ("user", "Ko'z oldimda chaqnash va qora parda"),
            ("assistant", "Og'riqsiz ko'rish pasaydimi?"),
            ("user", "Ha, periferiyadan parda tushyapti. Og'riq yo'q."),
        ),
        "ophthalmology", secondary=["emergency_medicine"],
        differentials=["retinal detachment", "PVD"], emergency=True,
    ),
    _case(
        "dc_080", "Red eye — common", "ophthalmology", "common",
        "Female, 30y, contact lens",
        _turns(
            ("user", "Ko'z qizarib, yosh ko'paygan"),
            ("assistant", "Ko'rish pasaydimi yoki og'riq bormi?"),
            ("user", "Og'riq bor, linza taqaman."),
        ),
        "ophthalmology", secondary=["emergency_medicine"],
        differentials=["keratitis", "conjunctivitis"], emergency=True,
    ),
    _case(
        "dc_081", "Giant cell arteritis — rare", "ophthalmology", "rare",
        "Female, 72y",
        _turns(
            ("user", "Chakkam og'riyapti, chaynashda og'riq"),
            ("assistant", "Ko'rish o'zgarish bormi?"),
            ("user", "Ha, bir ko'z ko'rmay qoldi bugun."),
        ),
        "ophthalmology", secondary=["emergency_medicine", "rheumatology"],
        differentials=["GCA", "stroke"], emergency=True,
    ),
    _case(
        "dc_082", "Diabetic retinopathy follow-up", "ophthalmology", "chronic_followup",
        "Male, 55y, diabetic",
        _turns(
            ("user", "Qandli diabetim bor, ko'rishim pasaygan"),
            ("assistant", "Oxirgi ko'z tekshiruvi qachon?"),
            ("user", "2 yil oldin. Endi ikki ko'z ham bulutli."),
        ),
        "ophthalmology", secondary=["endocrinology"],
        differentials=["diabetic retinopathy", "cataract"],
    ),
    _case(
        "dc_083", "Chemical eye injury", "ophthalmology", "emergency",
        "Male, 25y",
        _turns(
            ("user", "Ko'zimga kimyoviy modda tushdi, juda og'riyapti"),
            ("assistant", "Yuvdingizmi?"),
            ("user", "Ha, 15 daqiqa yuvdim. Hali og'riq kuchli."),
        ),
        "ophthalmology", secondary=["emergency_medicine"],
        differentials=["chemical burn", "corneal abrasion"], emergency=True,
    ),
    _case(
        "dc_084", "Patient minimizes vision loss", "ophthalmology", "misinformation",
        "Female, 70y",
        _turns(
            ("user", "Ko'z charchagan deb o'ylayman"),
            ("assistant", "Bir ko'z yoki ikkalasi?"),
            ("user", "Chap ko'z ko'rmayapti — 2 soat oldin birdan."),
            flags={2: (False, True)},
        ),
        "ophthalmology", secondary=["emergency_medicine", "neurology"],
        differentials=["retinal artery occlusion", "stroke"], emergency=True,
    ),
]

# --- Psychiatry (7) ---
_PSYCH = [
    _case(
        "dc_085", "Suicidal ideation", "psychiatry", "emergency",
        "Male, 28y",
        _turns(
            ("user", "O'zimni o'ldirmoqchi emasman lekin fikrlar keladi"),
            ("assistant", "Hozir xavf bormi?"),
            ("user", "Ha, dorilarim bor. Yolg'izman."),
        ),
        "psychiatry", secondary=["emergency_medicine"],
        differentials=["depression", "suicidal ideation"], emergency=True,
    ),
    _case(
        "dc_086", "Panic vs cardiac", "psychiatry", "multi_complaint",
        "Female, 35y",
        _turns(
            ("user", "Yurak urish, nafas qisish, o'lim qo'rquvi"),
            ("assistant", "Birinchi marta?"),
            ("user", "Ha. Qo'l uvyapti. 10 daqiqa davom etdi."),
        ),
        "emergency_medicine", secondary=["cardiology", "psychiatry"],
        differentials=["panic attack", "ACS", "PE"],
    ),
    _case(
        "dc_087", "First episode psychosis — rare presentation", "psychiatry", "rare",
        "Male, 22y",
        _turns(
            ("user", "Ovozlar eshitaman, kuzatilayotgandekman"),
            ("assistant", "Qachondan va uyqu qanday?"),
            ("user", "2 hafta. Uyqu kam, g'ayrioddiy ishontirishlar bor."),
        ),
        "psychiatry", differentials=["psychosis", "substance-induced", "organic"],
    ),
    _case(
        "dc_088", "Depression chronic follow-up", "psychiatry", "chronic_followup",
        "Female, 45y",
        _turns(
            ("user", "Depressiyam bor, dori yordam bermayapti"),
            ("assistant", "O'z joniga zarar fikri bormi?"),
            ("user", "Yo'q. Lekin ishga borolmayapman."),
        ),
        "psychiatry", differentials=["MDD", "treatment-resistant depression"],
    ),
    _case(
        "dc_089", "Substance withdrawal", "psychiatry", "common",
        "Male, 40y",
        _turns(
            ("user", "Spirt ichmay qo'ydim, qo'lim titrayapti"),
            ("assistant", "Qachondan ichmaysiz?"),
            ("user", "2 kun. Tush ko'ryapman, yurak tez uradi."),
        ),
        "psychiatry", secondary=["emergency_medicine"],
        differentials=["alcohol withdrawal", "DTs"], emergency=True,
    ),
    _case(
        "dc_090", "Hidden organic cause", "psychiatry", "hidden_red_flag",
        "Female, 60y",
        _turns(
            ("user", "Xotira yomonlashyapti, xulq o'zgardi"),
            ("assistant", "Qachondan va tezlik?"),
            ("user", "2 haftada keskin. Bosh og'rig'i va isitma ham bor."),
        ),
        "psychiatry", secondary=["neurology", "emergency_medicine", "infectious_diseases"],
        differentials=["delirium", "meningoencephalitis", "stroke"], emergency=True,
        hidden="Acute confusion + fever = organic first",
    ),
    _case(
        "dc_091", "Bipolar mania interruption", "psychiatry", "interruption",
        "Male, 30y",
        _turns(
            ("user", "Uyqu kerak emas —"),
            ("assistant", "Qancha vaqt uxlamaysiz?"),
            ("user", "— 3 kun! Juda ko'p gapiryapman, pul sarflayapman!"),
            flags={2: (True, False)},
        ),
        "psychiatry", differentials=["bipolar mania", "substance use"],
    ),
]

# --- Emergency Medicine (9) ---
_EMERGENCY = [
    _case(
        "dc_092", "Polytrauma", "emergency_medicine", "emergency",
        "Male, 30y",
        _turns(
            ("user", "Avtohalokat, ko'krak va qorin og'riyapti, qo'limda kuchli og'riq"),
            ("assistant", "Hush bormi?"),
            ("user", "Ha, lekin nafas qisish bor."),
        ),
        "emergency_medicine", secondary=["orthopedics", "general_surgery"],
        differentials=["trauma", "internal bleeding"], emergency=True,
    ),
    _case(
        "dc_093", "Altered mental status elderly", "emergency_medicine", "common",
        "Female, 78y",
        _turns(
            ("user", "Onam bugun boshqacha, javob bermayapti, isitmasi 38.5"),
            ("assistant", "Ilgari demensiya bormi?"),
            ("user", "Ha, lekin bugun yomonroq. Siydik hidli."),
        ),
        "emergency_medicine", secondary=["neurology", "infectious_diseases"],
        differentials=["UTI delirium", "stroke", "sepsis"], emergency=True,
    ),
    _case(
        "dc_094", "Intentional overdose", "emergency_medicine", "emergency",
        "Female, 22y",
        _turns(
            ("user", "Ko'p tabletka ichib qo'ydim, uyquchan, ko'ngil ayniyapti"),
            ("assistant", "Qaysi dori va qachon?"),
            ("user", "Paracetamol, 2 soat oldin. 20 ta."),
        ),
        "emergency_medicine", secondary=["psychiatry", "gastroenterology"],
        differentials=["paracetamol overdose", "suicide attempt"], emergency=True,
    ),
    _case(
        "dc_095", "Dual chest + neuro", "emergency_medicine", "multi_complaint",
        "Male, 62y",
        _turns(
            ("user", "Ko'krak og'rig'i va chap qo'lim uvyapti"),
            ("assistant", "Qachondan?"),
            ("user", "30 daqiqa. Qandli diabet va gipertoniya bor."),
        ),
        "emergency_medicine", secondary=["cardiology", "neurology"],
        red_flags=["chest_pain"], differentials=["ACS", "stroke"], emergency=True,
    ),
    _case(
        "dc_096", "Sepsis — hidden", "emergency_medicine", "hidden_red_flag",
        "Male, 70y",
        _turns(
            ("user", "Umumiy holsizlik, sovuq terlash"),
            ("assistant", "Isitma yoki nafas tezligi?"),
            ("user", "39.5, nafas 28. Qon bosim 90/50."),
        ),
        "emergency_medicine", secondary=["infectious_diseases"],
        differentials=["sepsis", "shock"], emergency=True,
        hidden="Hypotension + fever + tachypnea",
    ),
    _case(
        "dc_097", "Wrong reassurance request", "emergency_medicine", "misinformation",
        "Female, 45y",
        _turns(
            ("user", "Shunchaki tabletka kerak, ko'kragim og'riyapti"),
            ("assistant", "Og'riq qanday va qachondan?"),
            ("user", "Qattiq, chap qo'lga tarqaladi, 20 daqiqa. Terlab qoldim."),
            flags={2: (False, True)},
        ),
        "emergency_medicine", secondary=["cardiology"],
        red_flags=["chest_pain"], differentials=["ACS"], emergency=True,
        misinfo="Patient requests pills instead of emergency care",
    ),
    _case(
        "dc_098", "Heat stroke — rare", "emergency_medicine", "rare",
        "Male, 25y, athlete",
        _turns(
            ("user", "Mashq paytida hushim ketdi, juda issiq"),
            ("assistant", "Hozir hush bormi?"),
            ("user", "Ha. 41 isitma, teri quruq."),
        ),
        "emergency_medicine", differentials=["heat stroke", "exertional collapse"],
        emergency=True,
    ),
    _case(
        "dc_099", "Chronic disease ED visit", "emergency_medicine", "chronic_followup",
        "Male, 55y, COPD",
        _turns(
            ("user", "Surunkali yo'talim bor, bugun qon chiqdi"),
            ("assistant", "Nafas qisish qanchalik?"),
            ("user", "Hatto o'tirishda ham qiyin. 3 kun yomonlashdi."),
        ),
        "emergency_medicine", secondary=["pulmonology"],
        red_flags=["hemoptysis"], differentials=["COPD exacerbation", "lung cancer"],
        emergency=True,
    ),
    _case(
        "dc_100", "Multi-system collapse interruption", "emergency_medicine", "interruption",
        "Female, 50y",
        _turns(
            ("user", "Yomon his qilyapman —"),
            ("assistant", "Nima shikoyat?"),
            ("user", "— ko'krak og'rig'i! Keyin hushim ketdi bir daqiqa! Hozir yaxshiroq."),
            flags={2: (True, False)},
        ),
        "emergency_medicine", secondary=["cardiology", "neurology"],
        red_flags=["chest_pain"], differentials=["ACS", "syncope", "arrhythmia"],
        emergency=True,
    ),
]

ALL_CHALLENGE_TEMPLATES: list[ChallengeCase] = (
    _NEUROLOGY + _CARDIOLOGY + _INTERNAL + _PULMONOLOGY + _GASTRO + _ENDO
    + _UROLOGY + _GYNECO + _DERMA + _PEDIATRICS + _ENT + _OPHTHAL + _PSYCH + _EMERGENCY
)

assert len(ALL_CHALLENGE_TEMPLATES) == 100, f"Expected 100 cases, got {len(ALL_CHALLENGE_TEMPLATES)}"
