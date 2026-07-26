"""Trusted medical guideline catalog — WHO, NICE, AHA/ACC, ESC, ADA, KDIGO, GOLD, GINA, IDSA, ACOG, AAN, and specialty bodies."""

from __future__ import annotations

from app.medical_brain.evidence.types import GuidelineRule

# Comprehensive guideline rule bank — criteria distilled from published guidance
GUIDELINE_RULES: tuple[GuidelineRule, ...] = (
    # --- WHO ---
    GuidelineRule(
        "who_tb", "WHO", "WHO_TB_2022", "WHO TB diagnosis and urgency",
        criteria=(
            "Chronic cough >2 weeks with weight loss requires TB evaluation",
            "Hemoptysis mandates urgent chest imaging and infection workup",
            "Public health notification for confirmed or suspected TB",
        ),
        red_flags=("hemoptysis", "weight_loss", "night sweats"),
        required_actions=("chest imaging", "sputum", "urgent evaluation"),
        avoid=("attribute chronic cough to simple URI without duration assessment",),
        specialties=("pulmonology", "infectious_diseases", "internal_medicine"),
        match_patterns=("tb", "who tb", "tuberculosis", "tungi terlash", "hemoptysis", "yo'talda qon"),
    ),
    GuidelineRule(
        "who_anemia", "WHO", "WHO_ANEMIA", "WHO anemia assessment",
        criteria=(
            "Assess for iron deficiency cause including menstrual and GI blood loss",
            "Severe anemia with cardiovascular symptoms requires urgent evaluation",
        ),
        red_flags=("syncope", "chest pain", "severe fatigue"),
        required_actions=("CBC", "iron studies"),
        specialties=("internal_medicine", "hematology", "gynecology"),
        match_patterns=("anemia", "iron deficiency", "who anemia", "qon kam"),
    ),
    GuidelineRule(
        "who_dka", "WHO", "WHO_DKA", "WHO/ISPAD DKA emergency",
        criteria=(
            "Polyuria, vomiting, Kussmaul breathing → treat as DKA emergency",
            "Do not delay insulin/fluid resuscitation for extended history in unstable patient",
        ),
        red_flags=("dka", "kussmaul", "altered mental status"),
        required_actions=("emergency", "insulin", "fluids", "electrolytes"),
        avoid=("outpatient management of suspected DKA", "delay emergency care"),
        specialties=("endocrinology", "emergency_medicine", "pediatrics"),
        match_patterns=("dka", "who dka", "diabetic keto", "meva hid", "kussmaul"),
    ),
    # --- NICE ---
    GuidelineRule(
        "nice_headache", "NICE", "NICE_NG128", "NICE NG128 Headache disorders",
        criteria=(
            "Thunderclap headache → exclude subarachnoid hemorrhage urgently",
            "SNOOP red flags before benign headache diagnosis",
            "Do not delay emergency referral for sudden severe headache",
        ),
        red_flags=("thunderclap", "sudden severe headache", "focal neurology"),
        required_actions=("emergency neuroimaging", "exclude SAH"),
        avoid=("label thunderclap as migraine without exclusion", "delay imaging"),
        specialties=("neurology", "emergency_medicine"),
        match_patterns=("nice sah", "nice ng128", "thunderclap", "eng kuchli bosh", "headache"),
    ),
    GuidelineRule(
        "nice_weight_loss", "NICE", "NICE_WL", "NICE unexplained weight loss",
        criteria=(
            "Unexplained weight loss requires malignancy and organic disease screen",
            "Constitutional symptoms increase urgency of workup",
        ),
        red_flags=("weight_loss", "night sweats", "lymphadenopathy"),
        required_actions=("urgent workup", "malignancy screen"),
        specialties=("internal_medicine", "oncology"),
        match_patterns=("nice unexplained", "weight loss", "vazn yo'qot"),
    ),
    # --- AHA/ACC ---
    GuidelineRule(
        "aha_acs", "AHA/ACC", "AHA_ACS_2021", "AHA/ACC Acute coronary syndromes",
        criteria=(
            "Typical ACS features → immediate emergency pathway",
            "Assess radiation, diaphoresis, duration before non-cardiac diagnosis",
            "Time of onset critical for reperfusion decisions",
        ),
        red_flags=("chest_pain", "radiation", "diaphoresis", "syncope with chest pain"),
        required_actions=("emergency", "ECG", "troponin", "ACS pathway"),
        avoid=("attribute chest pain to reflux without cardiac exclusion", "delay ED"),
        specialties=("cardiology", "emergency_medicine"),
        match_patterns=("aha acs", "acc aha", "acs", "coronary", "ko'krak og'ri", "chap qo'l"),
    ),
    GuidelineRule(
        "aha_hf", "AHA/ACC", "AHA_HF", "ACC/AHA Heart failure",
        criteria=(
            "New or worsening dyspnea with edema → evaluate for decompensated HF",
            "Assess orthopnea, weight gain, medication adherence",
        ),
        required_actions=("BNP", "echocardiography", "diuresis when indicated"),
        specialties=("cardiology",),
        match_patterns=("acc/aha hf", "heart failure", "oyoq shish", "orthopnea"),
    ),
    # --- ESC ---
    GuidelineRule(
        "esc_pe", "ESC", "ESC_PE_2019", "ESC Pulmonary embolism",
        criteria=(
            "Sudden dyspnea with pleuritic pain or risk factors → PE until excluded",
            "Hemodynamic instability → emergency reperfusion pathway",
        ),
        red_flags=("sudden dyspnea", "hypotension", "syncope"),
        required_actions=("emergency", "CT-PA", "anticoagulation"),
        avoid=("discharge without PE rule-out when pretest probability high",),
        specialties=("pulmonology", "emergency_medicine", "cardiology"),
        match_patterns=("esc pe", "pulmonary embolism", "nafas qisish birdan"),
    ),
    GuidelineRule(
        "esc_af", "ESC", "ESC_AF", "ESC Atrial fibrillation",
        criteria=(
            "Assess stroke risk and anticoagulation need in AF",
            "Rate vs rhythm control based on hemodynamic stability",
        ),
        required_actions=("ECG", "stroke risk assessment"),
        specialties=("cardiology",),
        match_patterns=("esc af", "atrial fibrillation", "aritmiya"),
    ),
    GuidelineRule(
        "esc_vte", "ESC", "ESC_VTE", "ESC Venous thromboembolism",
        criteria=(
            "Unilateral leg swelling with PE symptoms → urgent VTE workup",
            "Anticoagulation unless contraindicated",
        ),
        red_flags=("unilateral leg swelling", "hemoptysis", "syncope"),
        required_actions=("D-dimer or imaging", "anticoagulation"),
        specialties=("hematology", "pulmonology", "emergency_medicine"),
        match_patterns=("esc vte", "dvt", "venous thrombo"),
    ),
    # --- ADA ---
    GuidelineRule(
        "ada_dka", "ADA", "ADA_DKA", "ADA Standards — DKA/HHS",
        criteria=(
            "Hyperglycemia with ketosis symptoms → DKA protocol",
            "Screen for infection as precipitant",
            "Never send unstable hyperglycemic patient home without ED assessment",
        ),
        red_flags=("dka", "hyperglycemia", "altered mental status"),
        required_actions=("emergency", "insulin", "fluids"),
        avoid=("outpatient insulin adjustment alone in DKA",),
        specialties=("endocrinology", "emergency_medicine"),
        match_patterns=("ada dka", "ada standards", "dka", "hhs"),
    ),
    GuidelineRule(
        "ada_screen", "ADA", "ADA_SCREEN", "ADA diabetes screening",
        criteria=(
            "Classic triad polyuria polydipsia weight loss → diabetes workup",
            "Hypoglycemia → treat immediately",
        ),
        required_actions=("glucose", "HbA1c when stable"),
        specialties=("endocrinology", "internal_medicine"),
        match_patterns=("ada", "diabetes", "polyuria", "ko'p siyaman"),
    ),
    # --- KDIGO ---
    GuidelineRule(
        "kdigo_aki", "KDIGO", "KDIGO_AKI", "KDIGO Acute kidney injury",
        criteria=(
            "Oliguria or rising creatinine → AKI staging and nephrotoxin review",
            "Life-threatening hyperkalemia → emergency treatment",
        ),
        red_flags=("anuria", "oliguria", "hyperkalemia", "pulmonary edema"),
        required_actions=("creatinine", "electrolytes", "renal ultrasound"),
        avoid=("high-dose NSAIDs in AKI", "delay nephrology when severe"),
        specialties=("nephrology", "emergency_medicine", "internal_medicine"),
        match_patterns=("kdigo aki", "kdigo", "aki", "oliguri", "siydik kamay"),
    ),
    GuidelineRule(
        "kdigo_gn", "KDIGO", "KDIGO_GN", "KDIGO Glomerular disease",
        criteria=(
            "Nephrotic-range proteinuria or active urinary sediment → nephrology referral",
            "Edema with reduced urine output needs urgent evaluation",
        ),
        required_actions=("urinalysis", "protein quantification", "nephrology"),
        specialties=("nephrology",),
        match_patterns=("kdigo glomerular", "nephrotic", "proteinuri"),
    ),
    # --- GOLD ---
    GuidelineRule(
        "gold_copd", "GOLD", "GOLD_2024", "GOLD COPD management",
        criteria=(
            "Increased dyspnea + purulent sputum → COPD exacerbation",
            "Severe dyspnea or hypoxia → emergency evaluation",
        ),
        red_flags=("severe dyspnea", "cyanosis", "altered mental status"),
        required_actions=("bronchodilator", "oxygen", "antibiotics if purulent"),
        specialties=("pulmonology", "emergency_medicine"),
        match_patterns=("gold copd", "gold", "copd", "surunkali yo'tal"),
    ),
    # --- GINA ---
    GuidelineRule(
        "gina_asthma", "GINA", "GINA_2024", "GINA Asthma",
        criteria=(
            "Assess exacerbation severity and response to bronchodilator",
            "Life-threatening asthma → emergency immediately",
        ),
        red_flags=("silent chest", "exhaustion", "altered consciousness"),
        required_actions=("peak flow or severity assessment", "bronchodilator", "ED if severe"),
        avoid=("repeated beta-agonist without assessing severity in acute asthma",),
        specialties=("pulmonology", "pediatrics", "emergency_medicine"),
        match_patterns=("gina", "asthma", "hushtak", "nafas qisish"),
    ),
    # --- IDSA ---
    GuidelineRule(
        "idsa_uti", "IDSA", "IDSA_UTI", "IDSA Urinary tract infection",
        criteria=(
            "Flank pain + fever → pyelonephritis not simple cystitis",
            "Urinary retention → urgent decompression",
            "Painless hematuria → exclude urologic malignancy",
        ),
        red_flags=("painless hematuria", "retention", "sepsis"),
        required_actions=("urinalysis", "culture", "urology if hematuria"),
        avoid=("single-dose antibiotic for pyelonephritis", "ignore painless hematuria"),
        specialties=("urology", "infectious_diseases"),
        match_patterns=("idsa uti", "idsa", "pyelonephritis", "cystitis", "siydik"),
    ),
    GuidelineRule(
        "idsa_cellulitis", "IDSA", "IDSA_SKIN", "IDSA Skin and soft tissue",
        criteria=(
            "Spreading erythema with fever → antibiotics; assess for necrotizing infection",
            "Systemic toxicity → emergency evaluation",
        ),
        red_flags=("spreading cellulitis", "sepsis", "crepitus"),
        required_actions=("antibiotics", "mark borders", "ED if systemic"),
        specialties=("dermatology", "infectious_diseases", "emergency_medicine"),
        match_patterns=("idsa cellulitis", "cellulitis", "qizarish kengay"),
    ),
    # --- ACOG / RCOG ---
    GuidelineRule(
        "acog_preeclampsia", "ACOG", "ACOG_HTN", "ACOG Hypertensive disorders of pregnancy",
        criteria=(
            "Headache, visual changes, epigastric pain in pregnancy → pre-eclampsia until excluded",
            "Severe hypertension in pregnancy → urgent obstetric evaluation",
        ),
        red_flags=("headache in pregnancy", "visual changes", "epigastric pain"),
        required_actions=("blood pressure", "proteinuria", "obstetric emergency"),
        avoid=("dismiss headache in third trimester as benign",),
        specialties=("obstetrics", "gynecology", "emergency_medicine"),
        match_patterns=("acog", "preeclampsia", "pre-eclampsia", "homilador.*bosh"),
    ),
    GuidelineRule(
        "rcog_bleed", "RCOG", "RCOG_AP", "RCOG Antepartum hemorrhage",
        criteria=(
            "Any bleeding in pregnancy → urgent obstetric assessment",
            "Assess fetal movement and hemodynamic stability",
        ),
        red_flags=("bleeding", "abdominal pain", "decreased fetal movement"),
        required_actions=("obstetric emergency", "fetal monitoring"),
        specialties=("obstetrics", "gynecology", "emergency_medicine"),
        match_patterns=("rcog", "antepartum", "homilador.*qon", "pregnancy bleeding"),
    ),
    # --- AAN ---
    GuidelineRule(
        "aan_stroke", "AAN", "AAN_STROKE", "AAN/AHA Stroke",
        criteria=(
            "Acute focal neurologic deficit → stroke pathway; time last known well",
            "Do not delay emergency care for prolonged symptom questionnaire",
        ),
        red_flags=("focal deficit", "speech disturbance", "facial weakness"),
        required_actions=("emergency", "stroke pathway", "time last well"),
        avoid=("delay thrombolysis workup for low-yield questions",),
        specialties=("neurology", "emergency_medicine"),
        match_patterns=("aan", "aha/asa stroke", "stroke", "insult", "qo'l kuchsiz"),
    ),
    GuidelineRule(
        "aan_migraine", "AAN", "AAN_MIGRAINE", "AAN Headache — exclude secondary first",
        criteria=(
            "Thunderclap or new headache pattern → secondary cause workup",
            "Red flags before primary headache diagnosis",
        ),
        red_flags=("thunderclap", "fever with headache", "papilledema"),
        specialties=("neurology",),
        match_patterns=("aan", "migraine", "headache"),
    ),
    # --- Surviving Sepsis / ACEP ---
    GuidelineRule(
        "ssc_sepsis", "Surviving Sepsis", "SSC_2021", "Surviving Sepsis Campaign",
        criteria=(
            "Suspected infection with organ dysfunction → sepsis bundle",
            "Hypotension after fluids → vasopressors and ICU",
        ),
        red_flags=("sepsis", "shock", "hypotension", "lactate"),
        required_actions=("blood cultures", "antibiotics", "fluids", "emergency"),
        avoid=("delay antibiotics for complete history in septic shock",),
        specialties=("intensive_care", "emergency_medicine", "infectious_diseases"),
        match_patterns=("surviving sepsis", "sepsis", "septik", "sovuq terlash"),
    ),
    # --- ATS / AAP / Other specialty ---
    GuidelineRule(
        "ats_dyspnea", "ATS", "ATS_DYSPNEA", "ATS Acute dyspnea",
        criteria=(
            "Acute dyspnea differential includes PE, ACS, asthma, pneumonia",
            "Hemoptysis requires urgent imaging",
        ),
        red_flags=("hemoptysis", "severe hypoxia"),
        required_actions=("oxygen", "ECG", "chest imaging"),
        specialties=("pulmonology", "emergency_medicine"),
        match_patterns=("ats", "dyspnea", "nafas qisish"),
    ),
    GuidelineRule(
        "aap_fever_infant", "AAP", "AAP_FEVER", "AAP Febrile infant",
        criteria=(
            "Fever in infant under 3 months → urgent comprehensive evaluation",
            "Full sepsis workup per age-based protocols",
        ),
        red_flags=("infant fever", "lethargy", "poor feeding"),
        required_actions=("emergency", "sepsis workup", "admission often required"),
        avoid=("outpatient observation alone for neonatal fever",),
        specialties=("pediatrics", "emergency_medicine"),
        match_patterns=("aap", "infant fever", "chaqaloq", "bolam.*isitma"),
    ),
    GuidelineRule(
        "aua_hematuria", "AUA", "AUA_HEM", "AUA Painless hematuria",
        criteria=(
            "Painless gross hematuria → urologic malignancy workup",
            "Cytology and imaging per guidelines",
        ),
        red_flags=("painless hematuria",),
        required_actions=("urology referral", "imaging", "cystoscopy pathway"),
        avoid=("treat as UTI without hematuria workup when painless",),
        specialties=("urology", "oncology"),
        match_patterns=("aua", "uspstf hematuria", "painless hematuria", "og'riqsiz qon"),
    ),
    GuidelineRule(
        "ash_itp", "ASH", "ASH_ITP", "ASH Immune thrombocytopenia",
        criteria=(
            "Mucocutaneous bleeding with low platelets → urgent hematology",
            "Headache or neuro symptoms with severe thrombocytopenia → emergency",
        ),
        red_flags=("purpura", "bleeding", "intracranial risk"),
        required_actions=("CBC", "peripheral smear", "hematology"),
        specialties=("hematology", "emergency_medicine"),
        match_patterns=("ash itp", "itp", "purpura", "petexi"),
    ),
    GuidelineRule(
        "eular_ra", "EULAR", "EULAR_RA", "EULAR Rheumatoid arthritis",
        criteria=(
            "Prolonged morning stiffness and symmetric small joint involvement → RA workup",
            "Early DMARD referral improves outcomes",
        ),
        required_actions=("RF/anti-CCP", "rheumatology"),
        specialties=("rheumatology",),
        match_patterns=("eular ra", "rheumatoid", "ertalab qattiq"),
    ),
    GuidelineRule(
        "nccn_cancer", "NCCN", "NCCN_RED", "NCCN Red flags for malignancy",
        criteria=(
            "Unexplained weight loss, hemoptysis, or fixed mass → expedited oncology workup",
            "Do not reassure without appropriate investigation",
        ),
        red_flags=("weight_loss", "hemoptysis", "fixed mass"),
        required_actions=("imaging", "biopsy pathway", "urgent referral"),
        specialties=("oncology", "internal_medicine"),
        match_patterns=("nccn", "malignancy", "cancer", "saraton"),
    ),
    GuidelineRule(
        "acep_trauma", "ACEP", "ACEP_TRAUMA", "ACEP Trauma triage",
        criteria=(
            "Major trauma → ABCDE primary survey first",
            "Altered consciousness → glucose, head injury, tox screen",
        ),
        required_actions=("emergency", "trauma activation", "minimal history until stable"),
        avoid=("detailed history before stabilization in major trauma",),
        specialties=("emergency_medicine", "general_surgery", "orthopedics"),
        match_patterns=("acep", "atls", "trauma", "avtohalokat"),
    ),
    GuidelineRule(
        "aao_glaucoma", "AAO", "AAO_GLAUC", "AAO Acute angle closure",
        criteria=(
            "Painful red eye with nausea → acute angle closure until excluded",
            "Same-day ophthalmology emergency",
        ),
        red_flags=("halos", "mid-dilated pupil", "severe eye pain"),
        required_actions=("IOP measurement", "ophthalmology emergency"),
        specialties=("ophthalmology", "emergency_medicine"),
        match_patterns=("aao glaucoma", "angle closure", "ko'z og'ri"),
    ),
)


def rules_for_specialty(specialty: str) -> list[GuidelineRule]:
    return [r for r in GUIDELINE_RULES if specialty in r.specialties or not r.specialties]


def all_sources() -> list[str]:
    return sorted({r.source for r in GUIDELINE_RULES})
