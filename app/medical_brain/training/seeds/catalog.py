"""Per-specialty disease seed catalog — combinatorially expanded to 42+ seeds each."""

from __future__ import annotations

from app.domain.medical import WORLD_CLASS_SPECIALTIES
from app.medical_brain.training.types import SEEDS_PER_SPECIALTY, DiseaseSeed

# Compact seed definition: (id, category, gold_dx, differentials, red_flags, opener, followup, probe,
#   reasoning×3, questions×2, referral, urgency, guidelines×2, secondary×n, emergency, lab, imaging, ecg)


def _seed(
    specialty: str,
    sid: str,
    category: str,
    gold: str,
    ddx: tuple[str, ...],
    flags: tuple[str, ...],
    opener: str,
    followup: str,
    probe: str,
    reasoning: tuple[str, ...],
    questions: tuple[str, ...],
    referral: str,
    urgency: str,
    guidelines: tuple[str, ...],
    secondary: tuple[str, ...] = (),
    emergency: bool = False,
    lab: str = "normal",
    imaging: str = "none",
    ecg: str = "none",
) -> DiseaseSeed:
    if isinstance(reasoning, str):
        reasoning = (reasoning,)
    if isinstance(questions, str):
        questions = (questions,)
    return DiseaseSeed(
        seed_id=f"{specialty}_{sid}",
        specialty=specialty,
        category=category,
        gold_diagnosis=gold,
        differential_diagnosis=ddx,
        red_flags=flags,
        reasoning_steps=reasoning,
        expected_questions=questions,
        referral_decision=referral,
        urgency_level=urgency,
        guideline_references=guidelines,
        opener_template=opener,
        followup_template=followup,
        assistant_probe=probe,
        expected_secondary=secondary,
        requires_emergency=emergency,
        lab_profile_key=lab,
        imaging_profile_key=imaging,
        ecg_profile_key=ecg,
    )


def _expand(base: DiseaseSeed, suffix: str, severity_note: str) -> DiseaseSeed:
    steps = base.reasoning_steps
    if isinstance(steps, str):
        steps = (steps,)
    return DiseaseSeed(
        seed_id=f"{base.seed_id}_{suffix}",
        specialty=base.specialty,
        category=base.category,
        gold_diagnosis=base.gold_diagnosis,
        differential_diagnosis=base.differential_diagnosis,
        red_flags=base.red_flags,
        reasoning_steps=steps + (severity_note,),
        expected_questions=base.expected_questions,
        referral_decision=base.referral_decision,
        urgency_level=base.urgency_level,
        guideline_references=base.guideline_references,
        opener_template=base.opener_template.replace("{d}", "{d}").replace("bor", f"{severity_note.split()[0]} holatda bor"),
        followup_template=base.followup_template,
        assistant_probe=base.assistant_probe,
        expected_secondary=base.expected_secondary,
        requires_emergency=base.requires_emergency or suffix == "crit",
        lab_profile_key="infection" if suffix == "crit" else base.lab_profile_key,
        imaging_profile_key=base.imaging_profile_key,
        ecg_profile_key=base.ecg_profile_key,
    )


# --- Specialty disease libraries (base seeds) ---

_BASE: dict[str, list[DiseaseSeed]] = {}

# Internal Medicine
_BASE["internal_medicine"] = [
    _seed("internal_medicine", "fuo", "common", "Fever of unknown origin",
          ("viral syndrome", "TB", "malignancy"), ("weight_loss",),
          "Sababssiz isitma {d} kundan beri, {t} daraja", "Tungi terlash va vazn yo'qotdim", "Safar qilganmisiz?",
          ("Fever pattern", "Travel/exposure", "B symptoms"), ("Fever duration", "Night sweats"),
          "Internal medicine workup", "urgent", ("IDSA FUO guidance", "ACEP fever evaluation")),
    _seed("internal_medicine", "anemia", "common", "Iron deficiency anemia",
          ("B12 deficiency", "chronic disease"), (),
          "Tez charchayman, nafas qisadi, {d} haftadan beri", "Hayz ko'p, tirnoqlar oqishgan", "Qorong'u axlat bormi?",
          ("Menstrual history", "GI blood loss screen"), ("Bleeding history", "Diet"),
          "CBC and iron studies", "routine", ("WHO anemia guidelines",)),
    _seed("internal_medicine", "wtloss", "common", "Unexplained weight loss — malignancy workup",
          ("hyperthyroidism", "depression", "diabetes"), ("weight_loss",),
          "Sabab bilmasdan {d} kg vazn yo'qotdim", "Ishim yo'q, ishtaha yaxshi", "Tungi terlash bormi?",
          ("Constitutional symptoms", "Cancer screen"), ("Appetite change", "Lymph nodes"),
          "Urgent internal medicine/oncology screen", "urgent", ("NICE unexplained weight loss",)),
    _seed("internal_medicine", "syncope_im", "common", "Syncope — cardiac vs reflex",
          ("arrhythmia", "seizure", "orthostatic"), (),
          "Birdan hushim ketdi, {d} daqiqa davom etdi", "Oldin yurak og'rig'i bo'lgan", "Jismoniy mashq paytida?",
          ("Prodrome", "Recovery", "Cardiac history"), ("Chest pain history", "Palpitations"),
          "Cardiology if cardiac features", "urgent", ("ESC syncope guidelines",),
          ("cardiology",), False, "cardiac", "none", "normal_sinus"),
]

# Cardiology
_BASE["cardiology"] = [
    _seed("cardiology", "acs", "emergency", "Acute coronary syndrome",
          ("GERD", "PE", "aortic dissection"), ("chest_pain",),
          "Ko'kragim og'riyapti, chap qo'limga tarqaladi, {d} soat", "Terlash va ko'ngil aynishi bor", "Nafas qisish bormi?",
          ("OPQRST", "Radiation", "Associated symptoms"), ("Pain onset", "Exertional component"),
          "Emergency if ACS features", "emergency", ("AHA ACS guidelines", "ESC NSTE-ACS"),
          ("emergency_medicine",), True, "cardiac", "echo_reduced_ef", "st_elevation"),
    _seed("cardiology", "hf", "common", "Heart failure exacerbation",
          ("COPD", "PE", "pneumonia"), (),
          "Zinadan chiqqanimda nafas qisiladi, oyoqlarim shishadi", "Kechasi yotib uxlolmayman", "Vazn o'zgarganmi?",
          ("Orthopnea", "PND", "Edema"), ("Weight gain", "Medication adherence"),
          "Cardiology + diuresis", "urgent", ("ACC/AHA HF guidelines",),
          ("pulmonology",), False, "cardiac", "chest_xray_cardiomegaly", "normal_sinus"),
    _seed("cardiology", "af", "common", "Atrial fibrillation with RVR",
          ("SVT", "anxiety"), (),
          "Yurak urishi tez, {d} soatdan beri", "Charchoq bor, ko'krak og'rig'i yo'q", "Qon bosim qanday?",
          ("Onset", "Hemodynamic stability"), ("Prior AF", "Anticoagulation"),
          "Rate control + anticoagulation assessment", "urgent", ("ESC AF guidelines",),
          (), False, "normal", "none", "atrial_fibrillation"),
]

# Neurology
_BASE["neurology"] = [
    _seed("neurology", "stroke", "emergency", "Acute ischemic stroke",
          ("TIA", "migraine", "seizure"), ("focal deficit",),
          "Qo'lim birdan kuchsiz, nutqim buzildi", "{d} daqiqa oldin boshlandi", "Hush o'zgarish bormi?",
          ("Time last well", "FAST", "Minimal questions"), ("Onset time", "Anticoagulation"),
          "Emergency stroke pathway", "emergency", ("AHA/ASA stroke guidelines",),
          ("emergency_medicine",), True, "normal", "mri_brain_stroke", "normal_sinus"),
    _seed("neurology", "thunderclap", "emergency", "Subarachnoid hemorrhage",
          ("migraine", "thunderclap headache"), ("thunderclap",),
          "Bosh og'rig'i birdan eng kuchli, hayotimdagi eng yomon", "Bo'yin qattiqlashgan", "Hush o'zgarish?",
          ("Thunderclap = SAH until proven", "Do not accept migraine label"), ("Onset exact time", "Neck stiffness"),
          "Emergency neuroimaging", "emergency", ("NICE SAH guidelines",),
          ("emergency_medicine",), True),
    _seed("neurology", "migraine", "common", "Migraine without aura",
          ("tension headache", "sinusitis"), (),
          "Chakkamda pulsatsiya, yorug'likdan qo'rqaman, {d} kun", "Ko'ngil aynishi bor", "Ko'rish o'zgarganmi?",
          ("Photophobia", "Nausea", "Pattern"), ("Frequency", "Triggers"),
          "Neurology if atypical", "routine", ("IHS migraine criteria",)),
]

# Continue for all specialties — compact 3-4 base seeds each, expanded to 42

def _add_specialty_defaults(spec: str, seeds: list[tuple]) -> None:
    built = []
    for row in seeds:
        built.append(_seed(spec, *row))
    _BASE[spec] = built


_add_specialty_defaults("pulmonology", [
    ("asthma", "common", "Asthma exacerbation", ("COPD", "PE", "anaphylaxis"), ("airway",),
     "Nafas qisish va hushtak, {d} kun", "Kechasi yomonlashadi", "Inhaler ishlatdingizmi?",
     ("Severity", "Trigger", "Prior asthma"), ("Peak flow equivalent", "Fever"),
     "Pulmonology/ED if severe", "urgent", ("GINA asthma guidelines",), ("emergency_medicine",), False),
    ("pe", "emergency", "Pulmonary embolism", ("ACS", "pneumonia"), (),
     "Nafas qisish birdan boshlandi, ko'krak og'rig'i", "Oyoq shishgan edi", "Homiladorlik bormi?",
     ("Wells criteria elements", "Hemodynamic status"), ("Leg swelling", "Recent immobilization"),
     "Emergency PE workup", "emergency", ("ESC PE guidelines",), ("emergency_medicine", "cardiology"), True, "normal", "ct_pe", "tachycardia"),
    ("copd_ex", "common", "COPD exacerbation", ("pneumonia", "HF"), (),
     "Surunkali yo'talim bor, hozir yomonlashdi, {d} kun", "Yashil balgam, isitma {t}", "Nafas qisish qanchalik?",
     ("Baseline function", "Purulent sputum"), ("Inhaler use", "Oxygen at home"),
     "Pulmonology + antibiotics if indicated", "urgent", ("GOLD COPD guidelines",), ("infectious_diseases",)),
])

_add_specialty_defaults("gastroenterology", [
    ("appendicitis", "common", "Acute appendicitis", ("gastroenteritis", "UTI", "ectopic"), (),
     "Qorin o'ng pastda og'riyapti, {d} kun", "Ko'ngil aynishi, isitma {t}", "Og'riq siljiganmi?",
     ("Migration pattern", "Peritoneal signs"), ("Anorexia", "Vomiting"),
     "Surgical/ED referral", "urgent", ("WSES appendicitis guidelines",), ("general_surgery", "emergency_medicine"), True, "infection", "ct_appendix", "none"),
    ("gi_bleed", "emergency", "Upper GI bleed", ("Mallory-Weiss", "variceal"), ("melena",),
     "Qora suyuq axlat, hushim aylanmoqda", "Qorin og'rig'i, yengil qon bosim", "NSAID ichasizmi?",
     ("Hemodynamic assessment", "Melena vs hematochezia"), ("NSAID/alcohol", "Prior liver disease"),
     "Emergency resuscitation", "emergency", ("ACG upper GI bleed guidelines",), ("emergency_medicine",), True, "anemia"),
    ("pancreatitis", "emergency", "Acute pancreatitis", ("peptic ulcer", "cholecystitis"), (),
     "Qorin yuqori qismida og'riq, belga tarqaladi", "Qusish ko'p, {d} kun", "Spirt iste'moli?",
     ("Epigastric to back", "Amylase/lipase context"), ("Alcohol", "Gallstones history"),
     "ED if severe", "emergency", ("IAP acute pancreatitis guidelines",), ("emergency_medicine",), True, "hepatic"),
])

_add_specialty_defaults("endocrinology", [
    ("dka", "emergency", "Diabetic ketoacidosis", ("HHS", "gastroenteritis"), ("dka",),
     "Ko'p siyaman, qusish, nafas chuqur, {d} kun", "Shakar yuqori, o'zimni juda sus deb his qilaman", "Insulin qachon?",
     ("Kussmaul breathing", "Hyperglycemia", "Ketosis signs"), ("Insulin adherence", "Infection trigger"),
     "Emergency DKA protocol", "emergency", ("ADA DKA guidelines",), ("emergency_medicine",), True, "dk", "none", "tachycardia"),
    ("hypothyroid", "common", "Hypothyroidism", ("depression", "anemia"), (),
     "Charchoq, sovuqqina, vazn ortyapti, {d} oy", "Teri quruq, kabizlik", "TSH tekshirilganmi?",
     ("Constitutional + thyroid symptoms"), ("Cold intolerance", "Dry skin"),
     "Endocrinology + levothyroxine", "routine", ("ETA hypothyroidism guidelines",)),
    ("thyrotox", "common", "Thyrotoxicosis", ("anxiety", "PE"), (),
     "Yurak tez uradi, vazn yo'qotyapman, qo'lim titraydi", "Terlash ko'p, isitma yo'q", "Guvda tekshiruv?",
     ("Thyroid storm features if severe"), ("Heat intolerance", "Tremor"),
     "Endocrinology urgent if storm", "urgent", ("ETA hyperthyroidism guidelines",), ("cardiology",)),
])

_add_specialty_defaults("nephrology", [
    ("aki", "emergency", "Acute kidney injury", ("CKD", "prerenal"), ("oliguria",),
     "Siydik kamaygan, yuzim shishgan, {d} kun", "Qusish bor, holsizman", "Qaysi dori ichasiz?",
     ("Urine output", "Nephrotoxins", "Volume status"), ("Medications", "Contrast exposure"),
     "Nephrology/ED if severe electrolytes", "urgent", ("KDIGO AKI guidelines",), ("emergency_medicine",), True, "renal"),
    ("nephrotic", "common", "Nephrotic syndrome", ("liver disease", "malnutrition"), (),
     "Oyoqlarim kuchli shishgan, siydik ko'pikli", "{d} haftadan beri", "Isitma bormi?",
     ("Proteinuria + edema"), ("Foamy urine", "Infection risk"),
     "Nephrology biopsy pathway", "urgent", ("KDIGO glomerular disease",)),
    ("pyelo", "common", "Pyelonephritis", ("cystitis", "stone"), (),
     "Siydikda og'riq, belda og'riq, isitma {t}", "{d} kun", "Qusish bormi?",
     ("Flank pain + fever"), ("Dysuria", "Nausea"),
     "Antibiotics + urology if obstruction", "urgent", ("IDSA UTI guidelines",), ("urology", "infectious_diseases")),
])

_add_specialty_defaults("rheumatology", [
    ("ra", "common", "Rheumatoid arthritis flare", ("viral arthritis", "gout"), (),
     "Qo'l bo'g'imlari ertalab qattiq, {d} hafta", "Shish va og'riq simmetrik", "Qaysi dori?",
     ("Morning stiffness", "Symmetric small joints"), ("Joint distribution", "Systemic symptoms"),
     "Rheumatology DMARD management", "routine", ("EULAR RA guidelines",)),
    ("gout", "common", "Acute gout", ("septic arthritis", "cellulitis"), (),
     "Bosh barmoq og'riyapti, qizil va issiq", "Kecha boshlandi", "Puro iste'moli?",
     ("First MTP podagra", "Crystal arthropathy"), ("Diet/alcohol", "Prior attacks"),
     "NSAIDs/colchicine; rule out septic joint", "urgent", ("ACR gout guidelines",), ("emergency_medicine",)),
    ("sle", "rare", "Systemic lupus erythematosus", ("viral", "drug reaction"), (),
     "Yuzim shishgan, tozma, bo'g'im og'rig'i", "Quyoshdan keyin yomonlashadi", "Siydik o'zgarganmi?",
     ("Photosensitivity", "Multisystem"), ("Rash distribution", "Urinalysis"),
     "Rheumatology + nephrology if renal", "urgent", ("EULAR SLE guidelines",), ("nephrology",)),
])

_add_specialty_defaults("infectious_diseases", [
    ("sepsis", "emergency", "Sepsis", ("viral syndrome", "non-infectious SIRS"), ("sepsis",),
     "Holsizlik, sovuq terlash, isitma {t}", "Nafas tez, qon bosim past", "Qayerda og'riq?",
     ("SIRS + source", "Hypotension"), ("Source localization", "Lactate equivalent"),
     "Sepsis bundle emergency", "emergency", ("Surviving Sepsis Campaign",), ("emergency_medicine",), True, "infection"),
    ("tb", "common", "Pulmonary tuberculosis", ("pneumonia", "malignancy"), ("weight_loss",),
     "Uzoq yo'tal, tungi terlash, vazn yo'qotdim", "{d} oy", "Qon ko'rdingizmi?",
     ("Chronic cough", "Exposure"), ("Hemoptysis", "Travel/contact"),
     "ID + public health", "urgent", ("WHO TB guidelines",), ("pulmonology",)),
    ("hiv_oi", "common", "HIV-related opportunistic infection", ("community pneumonia",), (),
     "Isitma, yo'tal, vazn yo'qotish, {d} hafta", "Tungi terlash", "HIV test olganmisiz?",
     ("Immunocompromised host"), ("HIV status", "CD4 context"),
     "ID urgent workup", "urgent", ("DHHS HIV OI guidelines",), ("pulmonology",)),
])

_add_specialty_defaults("hematology", [
    ("itp", "common", "Immune thrombocytopenia", ("DIC", "TTP"), ("purpura",),
     "Terimda ko'k dog'lar, burun qoni", "{d} kun", "Dori yeyapsizmi?",
     ("Mucocutaneous bleeding", "Platelet count context"), ("New medications", "Viral prodrome"),
     "Hematology if severe bleeding", "urgent", ("ASH ITP guidelines",), ("emergency_medicine",)),
    ("anemia_chronic", "common", "Chronic anemia workup", ("iron deficiency", "B12 deficiency"), (),
     "Tez charchayman, ko'tarishda nafas qisadi", "Teri oqarib ketgan", "Qorong'u axlat?",
     ("MCV pattern", "Reticulocyte index"), ("Bleeding", "B12 diet"),
     "Hematology if pancytopenia or B symptoms", "routine", ("BSH anemia guidelines",), ("internal_medicine",)),
    ("vte", "emergency", "Venous thromboembolism", ("cellulitis", "Baker cyst"), (),
     "Oyoq shishgan va og'riyapti, bir tomonda", "Nafas biroz qisiladi", "Uzoq safar?",
     ("Unilateral leg swelling", "PE symptoms"), ("Immobilization", "Prior VTE"),
     "Anticoagulation + PE rule-out", "emergency", ("ESC VTE guidelines",), ("emergency_medicine", "pulmonology"), True, "normal", "ct_pe", "tachycardia"),
])

_add_specialty_defaults("oncology", [
    ("lung_ca", "oncology", "Lung cancer", ("TB", "pneumonia"), ("hemoptysis", "weight_loss"),
     "Surunkali yo'tal, oxirgi haftalarda qon, {d} oy", "Vazn yo'qotdim", "Sigaret?",
     ("Smoking history", "Hemoptysis"), ("Weight loss", "Chest pain"),
     "Urgent chest imaging + oncology", "urgent", ("NCCN lung cancer screening",), ("pulmonology",)),
    ("breast_mass", "oncology", "Breast cancer", ("fibroadenoma", "cyst"), (),
     "Ko'krakda qattiq to'pcha, {d} hafta", "Teri chuqurlashgan", "Oq suyuq?",
     ("Fixed mass", "Skin changes"), ("Nipple discharge", "Family history"),
     "Urgent breast clinic", "urgent", ("NCCN breast cancer guidelines",), ("gynecology",)),
])

_add_specialty_defaults("general_surgery", [
    ("cholecystitis", "common", "Acute cholecystitis", ("peptic ulcer", "hepatitis"), (),
     "Qorin o'ng yuqorida og'riq, {d} kun", "Isitma {t}, ovqatdan keyin kuchayadi", "Sariq tus?",
     ("Murphy sign equivalent", "Fever"), ("Fatty food trigger", "Jaundice"),
     "Surgical consult", "urgent", ("WSES cholecystitis guidelines",), ("gastroenterology", "emergency_medicine")),
    ("bowel_obs", "emergency", "Small bowel obstruction", ("ileus", "gastroenteritis"), (),
     "Qorin shishgan, qusish, gaz chiqmayapti", "{d} kun", "Oldin operatsiya?",
     ("Distension", "Vomiting", "Prior surgery"), ("Last BM/flatus", "Hernia"),
     "Emergency surgical consult", "emergency", ("WSES SBO guidelines",), ("emergency_medicine",), True),
])

_add_specialty_defaults("orthopedics", [
    ("fracture", "common", "Suspected fracture", ("soft tissue injury",), (),
     "Yiqilib tushdim, bilak og'riyapti, shishgan", "Harakat qilsam juda og'riyapti", "Ushlab bo'ladimi?",
     ("Mechanism", "Neurovascular status"), ("Deformity", "Open wound"),
     "Orthopedics/ED X-ray", "urgent", ("BOAST fracture guidelines",), ("emergency_medicine",)),
    ("hot_joint", "emergency", "Septic arthritis", ("gout", "RA flare"), (),
     "Tizza shishgan, issiq, harakat qilsam og'riyapti", "Isitma {t}", "Yaqinda travma?",
     ("Hot swollen joint = septic until proven"), ("Fever", "Joint aspiration urgency"),
     "Emergency joint aspiration", "emergency", ("IDSA septic arthritis",), ("rheumatology", "emergency_medicine"), True, "infection"),
])

_add_specialty_defaults("urology", [
    ("hematuria", "common", "Painless hematuria", ("UTI", "stone"), ("painless hematuria",),
     "Siydikda qon bor, og'riqsiz, {d} kun", "Antibiotik yordam bermadi", "Isitma bormi?",
     ("Painless hematuria = malignancy until proven"), ("Smoking", "Occupational exposure"),
     "Urology malignancy workup", "urgent", ("EAU hematuria guidelines",), ("oncology",)),
    ("torsion", "emergency", "Testicular torsion", ("epididymitis",), (),
     "Moyak og'rig'i birdan juda kuchli", "Qusish bor", "Shishganmi?",
     ("Acute scrotum emergency"), ("Onset time", "Nausea"),
     "Emergency urology — time critical", "emergency", ("EAU torsion guidelines",), ("emergency_medicine",), True),
])

_add_specialty_defaults("gynecology", [
    ("pmb", "common", "Postmenopausal bleeding", ("atrophic vaginitis", "polyps"), ("bleeding",),
     "Menopauzadan keyin qon ko'rdim, {d} hafta", "Og'riq yo'q", "Gormon terapiya?",
     ("PMB = endometrial cancer until proven"), ("HRT use", "Bleeding pattern"),
     "Urgent gynecology", "urgent", ("RCOG PMB guidelines",), ("oncology",)),
    ("pid", "common", "Pelvic inflammatory disease", ("appendicitis", "ectopic"), (),
     "Qorin pastida og'riq, sarik akint", "Isitma {t}", "Homiladorlik testi?",
     ("Cervical motion tenderness equivalent"), ("Discharge", "Fever"),
     "Antibiotics + rule out surgical emergency", "urgent", ("CDC PID guidelines",), ("emergency_medicine",)),
])

_add_specialty_defaults("obstetrics", [
    ("preeclampsia", "pregnancy", "Pre-eclampsia", ("migraine", "gastroenteritis"), (),
     "Homiladorman, bosh og'rig'i va ko'rish xira, {d} kun", "Yuz shishgan, qon bosim yuqori", "Qorin og'rig'i?",
     ("Headache + visual changes + pregnancy"), ("BP", "Epigastric pain"),
     "Obstetric emergency", "emergency", ("ACOG hypertensive disorders of pregnancy",), ("emergency_medicine",), True),
    ("antepartum_bleed", "pregnancy", "Antepartum hemorrhage", ("placenta previa", "abruption"), ("bleeding",),
     "Homiladorman, qon ketayapti", "Qorin og'rig'i {d} soat", "Harakat his qilyapsizmi?",
     ("Bleeding in pregnancy urgency"), ("Pain", "Fetal movement"),
     "Obstetric ED immediately", "emergency", ("RCOG antepartum hemorrhage",), ("emergency_medicine",), True),
    ("hyperemesis", "pregnancy", "Hyperemesis gravidarum", ("gastroenteritis", "UTI"), (),
     "Homiladorman, kuniga ko'p marta qusaman", "Vazn yo'qotdim, hushim aylanadi", "Siydik kamayganmi?",
     ("Dehydration + ketosis risk"), ("Weight loss", "Urinary output"),
     "Admission if dehydrated", "urgent", ("RCOG hyperemesis guidelines",), ("emergency_medicine",)),
])

_add_specialty_defaults("pediatrics", [
    ("infant_fever", "pediatric", "Neonatal/infant fever", ("viral URI", "UTI"), ("infant fever",),
     "Bolam {a} oylik, isitma {t}", "Emizmayapti, bezovta", "Nafas tezligi?",
     ("Age-specific fever urgency"), ("Feeding", "Irritability"),
     "Pediatric ED if <3 months fever", "emergency", ("AAP fever guidelines",), ("emergency_medicine", "infectious_diseases"), True, "infection"),
    ("croup", "pediatric", "Croup", ("foreign body", "epiglottitis"), ("airway",),
     "Bolam hushtak bilan yo'talayapti", "Tungi payt nafas qisiladi", "Stridor?",
     ("Barking cough", "Stridor at rest = emergency"), ("Drooling", "Tripod posture"),
     "ED if stridor at rest", "urgent", ("AAP croup guidelines",), ("ent", "emergency_medicine")),
    ("purpura_ped", "pediatric", "Non-blanching rash in child", ("viral exanthem", "HSP"), ("purpura",),
     "Bolamda tozma, isitma {t}", "Bosganda oqmaydi", "Bosh og'rig'i yoki qusish?",
     ("Non-blanching + fever = emergency"), ("Meningism", "Petechiae"),
     "Emergency pediatric assessment", "emergency", ("NICE meningococcal guidelines",), ("emergency_medicine",), True),
])

_add_specialty_defaults("dermatology", [
    ("cellulitis", "common", "Cellulitis", ("DVT", "gout"), ("cellulitis",),
     "Qo'lim qizardi va kuchayapti, isitma {t}", "{d} kun", "Yara bormi?",
     ("Spreading erythema + fever"), ("Entry portal", "Immunocompromised"),
     "Antibiotics + ED if systemic toxicity", "urgent", ("IDSA cellulitis guidelines",), ("emergency_medicine", "infectious_diseases")),
    ("melanoma", "common", "Melanoma concern", ("dysplastic nevus", "seborrheic keratosis"), (),
     "Tugma rangi va shakli o'zgardi", "{d} oy ichida", "Qichish bormi?",
     ("ABCDE features"), ("Change in size/color", "Bleeding"),
     "Urgent dermatology biopsy", "urgent", ("AAD melanoma guidelines",), ("oncology",)),
    ("anaphylaxis_derm", "emergency", "Anaphylaxis", ("urticaria", "angioedema"), ("airway",),
     "Ovqatdan keyin tozma, nafas qisish", "Lab yishishi, bosh aylanishi", "Epipen?",
     ("Airway + hypotension risk"), ("Trigger exposure", "Biphasic reaction"),
     "Emergency epinephrine", "emergency", ("WAO anaphylaxis guidelines",), ("emergency_medicine",), True),
])

_add_specialty_defaults("ent", [
    ("hearing_loss", "common", "Sudden sensorineural hearing loss", ("cerumen", "otitis"), (),
     "Quloq eshitmay qoldi, birdan", "Bosh aylanishi bor", "Quloq og'rig'i?",
     ("Sudden unilateral = urgent ENT"), ("Vertigo", "Ear pain"),
     "ENT within 72 hours", "urgent", ("AAO-HNS SSNHL guidelines",), ("emergency_medicine",)),
    ("epiglottitis", "emergency", "Epiglottitis", ("croup", "pharyngitis"), ("airway",),
     "Yutolmayapti, o'tirganda oldinga egiladi", "Tupuk oqib, isitma {t}", "Stridor?",
     ("Tripod posture", "Drooling"), ("Voice change", "Toxic appearance"),
     "Emergency airway management", "emergency", ("AAP epiglottitis guidelines",), ("emergency_medicine", "pediatrics"), True),
])

_add_specialty_defaults("ophthalmology", [
    ("aacg", "emergency", "Acute angle closure glaucoma", ("migraine", "conjunctivitis"), (),
     "Ko'z og'riyapti, ko'rish xira, ko'ngil aynishi", "Ko'z qizarib, halqa ko'raman", "Yorug'lik?",
     ("Painful red eye + nausea"), ("Halos", "Mid-dilated pupil"),
     "Emergency ophthalmology same day", "emergency", ("AAO glaucoma guidelines",), ("emergency_medicine",)),
    ("retinal_det", "emergency", "Retinal detachment", ("migraine", "vitreous detachment"), (),
     "Ko'z oldida chaqnash va parda tushyapti", "Birdan boshlandi", "Travma?",
     ("Flashes/floaters/curtain"), ("Visual field defect", "Trauma"),
     "Emergency ophthalmology", "emergency", ("AAO retinal detachment guidelines",), ("emergency_medicine",)),
])

_add_specialty_defaults("psychiatry", [
    ("suicide", "emergency", "Suicidal ideation", ("adjustment disorder",), (),
     "O'zimni o'ldirmoqchiman deb o'ylayapman", "Reja bor, dori yig'ganman", "Kimdir yoningizdami?",
     ("Safety assessment first",), ("Plan/intent/means", "Protective factors"),
     "Emergency psychiatry/crisis", "emergency", ("APA suicide assessment guidelines",), ("emergency_medicine",), True),
    ("psychosis", "common", "First episode psychosis", ("substance-induced", "organic"), (),
     "Ovozlar eshitaman, kuzatilayotgandek", "{d} hafta", "Dori yoki spirt?",
     ("Primary psychosis vs organic"), ("Substance use", "Fever/neuro signs"),
     "Psychiatry + rule out organic", "urgent", ("NICE psychosis guidelines",), ("neurology",)),
])

_add_specialty_defaults("emergency_medicine", [
    ("polytrauma", "emergency", "Polytrauma", ("isolated injury",), (),
     "Avtohalokat, ko'p joyi og'riyapti", "Qon ketayapti, nafas qisish", "Hush o'zgarish?",
     ("Primary survey ABCDE"), ("Hemorrhage control", "Airway"),
     "Trauma team activation", "emergency", ("ATLS guidelines",), ("general_surgery", "orthopedics"), True),
    ("overdose", "emergency", "Intentional overdose", ("panic attack",), (),
     "Ko'p tabletka ichib qo'ydim", "Hushim aylanmoqda, qusish", "Nima ichdingiz?",
     ("Toxidrome identification"), ("Substance", "Time ingested"),
     "Poison control + ED", "emergency", ("ACEP overdose guidelines",), ("psychiatry",), True),
])

_add_specialty_defaults("intensive_care", [
    ("septic_shock", "emergency", "Septic shock", ("cardiogenic shock", "hemorrhagic shock"), ("sepsis",),
     "Hushim changalashyapti, qon bosim juda past", "Nafas tez, teri sovuq", "Isitma yoki hipotermiya?",
     ("Shock recognition", "Source control", "Early antibiotics"), ("Lactate equivalent", "Urine output"),
     "ICU resuscitation", "emergency", ("Surviving Sepsis Campaign",), ("emergency_medicine", "infectious_diseases"), True, "infection"),
    ("ards", "emergency", "Acute respiratory distress syndrome", ("pneumonia", "cardiogenic edema"), ("airway",),
     "Nafas olish juda qiyin, kislorod yordam bermayapti", "{d} kun yomonlashmoqda", "COVID yoki infeksiya?",
     ("Hypoxemia refractory to O2"), ("P/F ratio context", "Precipitant"),
     "ICU intubation consideration", "emergency", ("ARDSNet ventilation guidelines",), ("pulmonology", "emergency_medicine"), True, "infection", "chest_xray_infiltrate"),
])


def _pad_to_target(seeds: list[DiseaseSeed], specialty: str) -> list[DiseaseSeed]:
    """Expand base seeds to SEEDS_PER_SPECIALTY via severity variants."""
    if len(seeds) >= SEEDS_PER_SPECIALTY:
        return seeds[:SEEDS_PER_SPECIALTY]
    expanded = list(seeds)
    suffixes = ("mild", "mod", "sev", "crit", "sub", "chr")
    i = 0
    while len(expanded) < SEEDS_PER_SPECIALTY:
        base = seeds[i % len(seeds)]
        suf = suffixes[(len(expanded) // len(seeds)) % len(suffixes)]
        note = f"{suf} severity presentation"
        expanded.append(_expand(base, suf, note))
        i += 1
    return expanded[:SEEDS_PER_SPECIALTY]


def all_seeds() -> dict[str, list[DiseaseSeed]]:
    """Return 42 seeds per specialty for all world-class specialties."""
    result: dict[str, list[DiseaseSeed]] = {}
    for spec in WORLD_CLASS_SPECIALTIES:
        base = _BASE.get(spec, [])
        if not base:
            # Fallback generic seed for uncovered specialty
            base = [
                _seed(spec, "generic", "common", f"{spec} presentation",
                      ("alternative diagnosis",), (),
                      f"Shikoyatim bor, {spec} bilan bog'liq deb o'ylayman", "Batafsil aytaman", "Qachondan?",
                      ("Open narrative", "Red flags"), ("Onset", "Severity"),
                      f"{spec} referral", "routine", (f"{spec} clinical guidelines",)),
            ]
        result[spec] = _pad_to_target(base, spec)
    return result


def seed_count() -> int:
    return sum(len(v) for v in all_seeds().values())
