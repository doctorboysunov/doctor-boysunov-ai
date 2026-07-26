"""Published clinical guideline references for real-world validation."""

from __future__ import annotations

# Guideline source catalog — informs case design and scoring, not scripted responses.
GUIDELINE_SOURCES: dict[str, str] = {
    "NICE_NG128": "NICE NG128 — Headache disorders (red flags, SAH, temporal arteritis)",
    "AHA_ACS_2021": "AHA/ACC 2021 — Acute coronary syndromes (chest pain evaluation)",
    "ADA_STANDARDS_2024": "ADA Standards of Care 2024 — Diabetes screening and acute complications",
    "GOLD_COPD_2024": "GOLD 2024 — COPD assessment and exacerbation management",
    "ACG_GI_BLEED": "ACG Guideline — Upper/lower GI bleeding management",
    "IDSA_UTI_2010": "IDSA 2010 — Uncomplicated/complicated UTI and pyelonephritis",
    "RCOG_ECTOPIC": "RCOG Green-top — Ectopic pregnancy and early pregnancy loss",
    "AAD_RASH_FEVER": "AAD — Drug eruption and cellulitis evaluation",
    "AAP_FEVER_INFANT": "AAP 2021 — Febrile infant evaluation (age-stratified)",
    "AAOS_BACK_PAIN": "AAOS — Low back pain red flags and cauda equina",
    "ACEP_TRAUMA": "ACEP — Trauma and altered mental status triage",
    "WHO_DKA": "WHO/ISPAD — Diabetic ketoacidosis and hypoglycemia emergency",
    "ESC_SYNCope": "ESC 2018 — Syncope evaluation and risk stratification",
    "ATS_DYSPNEA": "ATS — Acute dyspnea differential (PE, ACS, asthma)",
    "USPSTF_HEMATURIA": "AUA/USPSTF — Painless hematuria malignancy workup",
}


def criteria_for(source_key: str) -> list[str]:
    """Return validation criteria derived from published guidelines."""
    catalog: dict[str, list[str]] = {
        "NICE_NG128": [
            "Thunderclap headache → exclude subarachnoid hemorrhage urgently",
            "SNOOP red flags before benign headache workup",
            "Do not delay emergency referral for sudden severe headache",
        ],
        "AHA_ACS_2021": [
            "Typical ACS features → immediate emergency pathway",
            "Assess radiation, diaphoresis, duration before non-cardiac diagnosis",
            "Time of onset critical for reperfusion decisions",
        ],
        "ADA_STANDARDS_2024": [
            "Polyuria/polydipsia/weight loss → screen for diabetes",
            "Hypoglycemia with altered mental status → emergency treatment",
            "Diabetes + neuropathy → coordinate endocrine and neurologic care",
        ],
        "GOLD_COPD_2024": [
            "Increased dyspnea + purulent sputum → exacerbation",
            "Severe dyspnea or hypoxia → emergency evaluation",
            "Distinguish asthma from COPD by history and pattern",
        ],
        "ACG_GI_BLEED": [
            "Melena or hematemesis → urgent GI evaluation",
            "Hemodynamic instability → emergency resuscitation first",
            "RLQ pain with fever → appendicitis in differential",
        ],
        "IDSA_UTI_2010": [
            "Flank pain + fever → pyelonephritis, not simple UTI",
            "Urinary retention → catheterization urgency",
            "Painless hematuria → exclude urologic malignancy",
        ],
        "RCOG_ECTOPIC": [
            "Positive pregnancy test + pain → ectopic until excluded",
            "Pregnancy bleeding → emergency OB evaluation",
            "Postmenopausal bleeding → endometrial malignancy workup",
        ],
        "AAD_RASH_FEVER": [
            "Spreading erythema + fever → cellulitis vs necrotizing infection",
            "Rash + angioedema + dyspnea → anaphylaxis emergency",
            "Changing mole → melanoma red flags (ABCDE)",
        ],
        "AAP_FEVER_INFANT": [
            "Fever in infant <3 months → urgent evaluation",
            "Febrile seizure → assess for serious bacterial infection",
            "Dehydration signs in child → same-day assessment",
        ],
        "AAOS_BACK_PAIN": [
            "Saddle anesthesia, urinary retention → cauda equina emergency",
            "Hot swollen joint → septic arthritis until proven otherwise",
            "Trauma + neurovascular deficit → urgent imaging",
        ],
        "ACEP_TRAUMA": [
            "Major trauma → ABCDE, minimal history before stability",
            "Altered consciousness → glucose, stroke, tox screen",
            "Active severe bleeding → direct pressure and emergency care",
        ],
        "WHO_DKA": [
            "Polyuria + vomiting + Kussmaul breathing → DKA emergency",
            "Hypoglycemia → treat immediately, do not delay for history",
        ],
        "ESC_SYNCope": [
            "Syncope during exertion → cardiac cause until excluded",
            "Chest pain + syncope → ACS pathway",
            "Witnessed seizure activity → neurologic evaluation",
        ],
        "ATS_DYSPNEA": [
            "Acute dyspnea + pleuritic chest pain → PE in differential",
            "Hemoptysis → malignancy, TB, PE workup",
            "Wheezing → assess severity and response to bronchodilator",
        ],
        "USPSTF_HEMATURIA": [
            "Painless gross hematuria → urologic malignancy workup",
            "Testicular pain sudden onset → torsion until excluded",
        ],
    }
    return catalog.get(source_key, ["Apply specialty-appropriate clinical reasoning"])
