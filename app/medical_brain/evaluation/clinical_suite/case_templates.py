"""500 clinical case templates — 11 major specialties."""

from __future__ import annotations

# Each entry: suffix, title, message, expected_primary, kwargs
CaseSeed = tuple[str, str, str, str, dict]

SPECIALTY_ORDER = (
    "neurology",
    "cardiology",
    "endocrinology",
    "gastroenterology",
    "pulmonology",
    "urology",
    "gynecology",
    "dermatology",
    "pediatrics",
    "orthopedics",
    "emergency_medicine",
)

CASES_PER_SPECIALTY = 45  # 11 * 45 = 495 + 5 anchors = 500

_TEMPLATES: dict[str, list[CaseSeed]] = {
    "neurology": [
        ("headache_general", "General headache", "Boshim og'riyapti", "neurology", {"expected_reasoning": "Open narrative then SNOOP red flags", "expert_priority_phase": "narrative", "forbidden_questions": ["1-10", "qachondan"], "improvement_hint": "Reflect complaint; ask onset pattern not severity scale first"}),
        ("migraine", "Migraine with aura features", "Chakkamda pulsatsiya, ko'ngil aynish, yorug'likdan qo'rqaman", "neurology", {"expected_reasoning": "Confirm migraine features; ask frequency", "forbidden_questions": ["peshona"], "improvement_hint": "Acknowledge photophobia/nausea already given"}),
        ("thunderclap", "Thunderclap headache", "Boshim birdan juda qattiq og'riyapti, hayotimdagi eng kuchli og'riq", "neurology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expected_red_flags": ["thunderclap", "sudden"], "expert_priority_phase": "triage", "expected_referral": "Emergency ED immediately", "improvement_hint": "Triage SAH before location questions"}),
        ("stroke", "Acute stroke symptoms", "Qo'lim kuchsiz, nutqim buzildi, 1 soat oldin boshlandi", "neurology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage", "expected_referral": "Emergency stroke pathway", "improvement_hint": "Time last well; minimal questions"}),
        ("vertigo_bppv", "Positional vertigo", "Bosh aylanishi bor, faqat boshimni burgsam 30 soniya davom etadi", "neurology", {"expected_reasoning": "Episodic positional pattern — BPPV", "forbidden_questions": ["qachondan"], "improvement_hint": "Ask episode duration and position trigger first"}),
        ("vertigo_central", "Central vertigo red flags", "Doimiy bosh aylanishi, yurish qiyin, bosh og'riyapti", "neurology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage", "improvement_hint": "Screen central signs before peripheral"}),
        ("neuropathy_dm", "Diabetic neuropathy", "Qandli diabetim bor, oyoqlarim uvyapti", "neurology", {"expected_secondary": ["endocrinology"], "requires_multi_specialty": True, "expected_reasoning": "Stocking-glove pattern + diabetes control", "improvement_hint": "Coordinate endocrine and neuro"}),
        ("seizure_first", "First seizure", "Hushim ketdi deb ayishyapti, tilim qisilgan", "neurology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage", "improvement_hint": "Seizure triage not headache workup"}),
        ("back_cauda", "Cauda equina concern", "Bel og'riyapti, oyoqlarim uiydi, hojatxonaga qiyin", "neurology", {"requires_emergency": True, "expected_red_flags": ["cauda"], "expert_priority_phase": "triage", "improvement_hint": "Bladder/bowel before chronicity"}),
        ("memory", "Memory impairment", "Xotiram yomonlashyapti, pul va dori nomlarini unutaman", "neurology", {"expected_reasoning": "Functional impact, gradual vs sudden, informant", "improvement_hint": "ADL questions not mini-mental in chat"}),
        ("tremor_rest", "Rest tremor", "Qo'lim dam olganda titraydi, harakatda yaxshilanadi", "neurology", {"expected_reasoning": "Rest vs action; parkinsonism screen", "improvement_hint": "Follow rest tremor clue to bradykinesia/gait"}),
        ("facial_palsy", "Facial weakness", "Yuzim bir tomonda qiyshayapti", "neurology", {"expected_reasoning": "Forehead sparing vs full face — stroke vs Bell's", "expert_priority_phase": "discriminator", "improvement_hint": "Forehead movement question early"}),
    ],
    "cardiology": [
        ("acs", "Chest pain ACS", "Ko'kragim og'riyapti, chap qo'limga tarqaladi", "cardiology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expected_referral": "Emergency if ACS features", "improvement_hint": "OPQRST + radiation before generic pain scale"}),
        ("palpitations", "Palpitations", "Yurak urishim tezlashyapti, ko'kragimda g'ovak", "cardiology", {"expected_reasoning": "Onset, duration, syncope, caffeine/meds"}),
        ("heart_failure", "Dyspnea on exertion", "Zinadan chiqqanimda nafas qisiladi, oyoqlarim shishadi", "cardiology", {"expected_secondary": ["pulmonology"], "expected_reasoning": "Orthopnea, PND, edema, cardiac history"}),
        ("hypertension", "Uncontrolled BP", "Qon bosimim yuqori, bosim 180/110", "cardiology", {"expected_reasoning": "Symptoms of end-organ damage, meds adherence"}),
        ("syncope", "Syncope", "Birdan hushim ketdi, 1 daqiqa", "cardiology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine", "neurology"], "expert_priority_phase": "triage"}),
        ("atypical_chest", "Atypical chest discomfort", "Ko'kragimda bosim, stress paytida", "cardiology", {"expected_reasoning": "Still screen cardiac features in atypical presentation"}),
    ],
    "endocrinology": [
        ("diabetes_new", "New diabetes symptoms", "Ko'p ichaman, ko'p siyaman, vazn yo'qotyapman", "endocrinology", {"expected_reasoning": "Polyuria polydipsia weight loss — DKA screen"}),
        ("diabetes_control", "Poor diabetes control", "Qandli diabetim bor, shakarim doim yuqori", "endocrinology", {"expected_reasoning": "HbA1c equivalent questions, complications screen"}),
        ("hypoglycemia", "Hypoglycemia", "Shakar tushib ketdi, titroq va terlash", "endocrinology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("thyroid_hyper", "Hyperthyroid symptoms", "Yurak tez uradi, vazn yo'qotyapman, qo'lim titraydi", "endocrinology", {"expected_secondary": ["cardiology"], "expected_reasoning": "Thyroid storm features if severe"}),
        ("thyroid_hypo", "Hypothyroid symptoms", "Charchoq, sovuqqina, vazn ortyapti", "endocrinology", {"expected_reasoning": "Constitutional + thyroid history"}),
        ("adrenal", "Possible adrenal crisis", "Kuchli zaiflik, qorin og'riyapti, qon bosim past", "endocrinology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"]}),
    ],
    "gastroenterology": [
        ("abd_general", "Abdominal pain", "Qorin og'riyapti", "gastroenterology", {"expected_reasoning": "Location, character, vomiting, alarm features"}),
        ("gi_bleed", "GI bleeding", "Qorong'u axlat, qorin og'riyapti", "gastroenterology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("appendicitis", "RLQ pain", "Qorin o'ng pastda og'riyapti, ko'ngil aynish", "gastroenterology", {"expected_secondary": ["general_surgery", "emergency_medicine"], "requires_emergency": True}),
        ("reflux", "GERD symptoms", "Ko'kragimda kuydirish, ovqatdan keyin", "gastroenterology", {"expected_reasoning": "Alarm features before treating as simple reflux"}),
        ("hepatitis", "Jaundice", "Ko'zlarim sariq, qorin o'ng tomonda og'riq", "gastroenterology", {"expected_reasoning": "Jaundice + fever = urgent"}),
        ("pancreatitis", "Epigastric pain radiating back", "Qorin yuqori qismida og'riq, belga tarqaladi", "gastroenterology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"]}),
    ],
    "pulmonology": [
        ("dyspnea_acute", "Acute dyspnea", "Nafas olishim qiyinlashyapti", "pulmonology", {"expected_secondary": ["emergency_medicine", "cardiology"], "requires_emergency": True, "expert_priority_phase": "triage"}),
        ("asthma", "Asthma exacerbation", "Nafas qisilish, hushtak chiqyapti", "pulmonology", {"expected_reasoning": "Severity, trigger, inhaler use"}),
        ("copd", "COPD worsening", "Surunkali yo'talim bor, hozir yomonlashdi", "pulmonology", {"expected_reasoning": "Purulent sputum, fever, baseline function"}),
        ("hemoptysis", "Coughing blood", "Yo'tal paytida qon chiqyapti", "pulmonology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("pe", "Possible PE", "Nafas qisish va ko'krak og'rig'i, uzoq safar qilganman", "pulmonology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine", "cardiology"]}),
        ("chronic_cough", "Chronic cough", "3 haftadan beri yo'talim bor", "pulmonology", {"expected_reasoning": "Duration, smoking, weight loss, hemoptysis"}),
    ],
    "urology": [
        ("uti", "Dysuria", "Siydik qilishda og'riq bor", "urology", {"expected_reasoning": "Frequency, fever, flank pain"}),
        ("hematuria", "Painless hematuria", "Siydikda qon bor, og'riqsiz", "urology", {"expected_referral": "Urology workup for malignancy", "expected_reasoning": "Painless hematuria is red flag"}),
        ("retention", "Urinary retention", "Siydik chiqmayapti, qorin shishgan", "urology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"]}),
        ("stone", "Renal colic", "Belda o'tkir og'riq, siydikda qon", "urology", {"expected_reasoning": "Colic pattern, nausea, fever"}),
        ("prostate", "Prostate symptoms", "Siydik oqimi zaif, kechasi ko'p turaman", "urology", {"expected_reasoning": "IPSS equivalent, hematuria screen"}),
        ("testicular", "Testicular pain", "Moyak og'riyapti, birdan boshlandi", "urology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
    ],
    "gynecology": [
        ("pelvic_pain", "Pelvic pain", "Qorin pastida og'riq", "gynecology", {"expected_reasoning": "LMP, pregnancy, fever"}),
        ("pregnancy_bleed", "Pregnancy bleeding", "Homiladorman, qon ketayapti", "gynecology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("menorrhagia", "Heavy periods", "Hayz juda ko'p va uzoq davom etadi", "gynecology", {"expected_reasoning": "Anemia symptoms, fibroid history"}),
        ("menopause_bleed", "Postmenopausal bleeding", "Menopauzadan keyin qon ko'rdim", "gynecology", {"expected_referral": "Urgent gynecology — malignancy until proven", "expected_reasoning": "Postmenopausal bleeding is red flag"}),
        ("vaginal_discharge", "Abnormal discharge", "Sarik akint bor, qichish", "gynecology", {"expected_reasoning": "Odor, fever, pregnancy status"}),
        ("ectopic", "Ectopic concern", "Homiladorlik testi ijobiy, qattiq qorin og'rig'i", "gynecology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"]}),
    ],
    "dermatology": [
        ("rash_general", "New rash", "Terimda tozma chiqdi", "dermatology", {"expected_reasoning": "Distribution, progression, itch, meds"}),
        ("rash_fever", "Rash with fever", "Tozma va isitma bor", "dermatology", {"expected_secondary": ["infectious_diseases"], "requires_multi_specialty": True, "expected_reasoning": "Systemic infection vs drug reaction"}),
        ("cellulitis", "Spreading redness", "Qo'lim qizardi va kuchayapti, isitma bor", "dermatology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine", "infectious_diseases"]}),
        ("anaphylaxis", "Urticaria after food", "Ovqatdan keyin tozma, nafas qisish", "dermatology", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("melanoma", "Changing mole", "Tugma rangi va shakli o'zgardi", "dermatology", {"expected_referral": "Dermatology urgent biopsy", "expected_reasoning": "ABCDE features"}),
        ("shingles", "Dermatomal rash", "Ko'kragimning bir tomonida tozma va og'riq", "dermatology", {"expected_reasoning": "Dermatomal pattern, immunocompromised"}),
    ],
    "pediatrics": [
        ("fever_infant", "Infant fever", "Bolam 6 oylik, isitmasi 38.5", "pediatrics", {"expected_secondary": ["infectious_diseases"], "requires_emergency": True, "expected_reasoning": "Age-specific fever urgency"}),
        ("child_cough", "Child cough", "Bolam 4 yosh, yo'talayapti", "pediatrics", {"expected_reasoning": "Hydration, breathing difficulty, fever"}),
        ("child_rash", "Child rash fever", "Bolamda tozma va isitma", "pediatrics", {"expected_secondary": ["dermatology", "infectious_diseases"], "requires_multi_specialty": True}),
        ("dehydration", "Dehydration", "Bola qusyapti, ichmayapti, kam siydiyapti", "pediatrics", {"requires_emergency": True, "expected_secondary": ["emergency_medicine"], "expert_priority_phase": "triage"}),
        ("febrile_seizure", "Febrile seizure", "Bola isitmada tutqanoq tutdi", "pediatrics", {"requires_emergency": True, "expected_secondary": ["neurology", "emergency_medicine"]}),
        ("development", "Development delay", "Bolam 2 yoshda gapirmayapti", "pediatrics", {"expected_reasoning": "Milestone history, hearing screen"}),
    ],
    "orthopedics": [
        ("knee_pain", "Knee pain", "Tizza og'riyapti", "orthopedics", {"expected_reasoning": "Trauma, swelling, locking"}),
        ("hot_joint", "Hot swollen joint", "Tizza shishgan va issiq", "orthopedics", {"expected_secondary": ["rheumatology", "emergency_medicine"], "requires_emergency": True, "expert_priority_phase": "triage"}),
        ("fracture", "Suspected fracture", "Yiqilib tushdim, bilak og'riyapti, shishgan", "orthopedics", {"requires_emergency": True, "expected_reasoning": "Neurovascular status, deformity"}),
        ("back_mechanical", "Mechanical back pain", "Bel og'riyapti, og'ir ko'targanda", "orthopedics", {"expected_secondary": ["neurology"], "expected_reasoning": "Red flags before mechanical diagnosis"}),
        ("shoulder", "Shoulder pain", "Yelka og'riyapti, qo'limni ko'tara olmayman", "orthopedics", {"expected_reasoning": "Trauma, ROM, night pain"}),
        ("sciatica", "Sciatica", "Bel og'riyapti, oyoqqa tarqaladi", "orthopedics", {"expected_secondary": ["neurology"], "expected_reasoning": "Radiculopathy vs cauda equina"}),
    ],
    "emergency_medicine": [
        ("chest_emergency", "Chest pain emergency", "Ko'krak og'rig'i va nafas qisish", "emergency_medicine", {"requires_emergency": True, "expected_secondary": ["cardiology", "pulmonology"]}),
        ("trauma", "Major trauma", "Avtohalokat, ko'p joyi og'riyapti", "emergency_medicine", {"requires_emergency": True, "expert_priority_phase": "triage"}),
        ("anaphylaxis_em", "Anaphylaxis", "Arachis yedim, nafas qisildi, tozma", "emergency_medicine", {"requires_emergency": True, "expected_secondary": ["dermatology"]}),
        ("altered_mental", "Altered consciousness", "Onam hushsiz, javob bermayapti", "emergency_medicine", {"requires_emergency": True, "expected_secondary": ["neurology"]}),
        ("severe_bleeding", "Severe bleeding", "Ko'p qon ketayapti, bandaj qon tomayapti", "emergency_medicine", {"requires_emergency": True, "expert_priority_phase": "triage"}),
        ("overdose", "Overdose", "Ko'p tabletka ichib qo'ydim", "emergency_medicine", {"requires_emergency": True, "expected_secondary": ["psychiatry"]}),
    ],
}

# Five anchor cases spanning multi-specialty emergencies
_ANCHOR_CASES: list[CaseSeed] = [
    ("anchor_dm_neuro", "Diabetes + neuropathy combo", "Diabetim bor, qo'lim va oyoqlarim uvyapti", "endocrinology", {"expected_secondary": ["neurology"], "requires_multi_specialty": True, "expected_reasoning": "Endocrine control AND neuropathy pattern"}),
    ("anchor_chest_arm", "Chest pain + arm numbness", "Ko'krak og'rig'i va qo'lim uvyapti", "emergency_medicine", {"expected_secondary": ["cardiology", "neurology"], "requires_emergency": True}),
    ("anchor_rash_fever", "Rash + fever systemic", "Butun tana tozma, isitma 39", "dermatology", {"expected_secondary": ["infectious_diseases", "emergency_medicine"], "requires_emergency": True}),
    ("anchor_child_fever", "Neonate fever", "Chaqaloq 1 oylik, isitma 38", "pediatrics", {"expected_secondary": ["emergency_medicine"], "requires_emergency": True}),
    ("anchor_cauda", "Cauda equina emergency", "Bel og'riq, ikkala oyoq uysin, siydik tutib qoldi", "neurology", {"expected_secondary": ["emergency_medicine", "orthopedics"], "requires_emergency": True, "expert_priority_phase": "triage"}),
]
