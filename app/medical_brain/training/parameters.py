"""Combinatorial parameter space for clinical case generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.medical_brain.training.types import CaseParameters

# --- Variation pools ---

OCCUPATIONS = (
    "office worker", "farmer", "teacher", "driver", "healthcare worker",
    "construction worker", "student", "retired", "factory worker", "merchant",
)

CHRONIC_CONDITIONS = (
    "hypertension", "type 2 diabetes", "COPD", "CKD stage 3", "coronary artery disease",
    "atrial fibrillation", "hypothyroidism", "obesity", "asthma", "GERD",
    "rheumatoid arthritis", "HIV", "cirrhosis", "heart failure", "anemia",
)

MEDICATIONS = (
    "metformin", "amlodipine", "aspirin", "warfarin", "insulin",
    "levothyroxine", "salbutamol inhaler", "omeprazole", "prednisolone", "no regular medications",
)

RISK_FACTORS = (
    "smoking", "alcohol use", "family history of cancer", "recent travel",
    "immunosuppression", "sedentary lifestyle", "high salt diet", "occupational exposure",
    "prior DVT", "no significant risk factors",
)

SEVERITY_LEVELS = ("mild", "moderate", "severe", "critical")
PROGRESSION_TYPES = ("acute", "subacute", "chronic", "relapsing")
PREGNANCY_STATES = ("none", "pregnant", "postpartum")

LAB_PROFILES: dict[str, dict[str, str]] = {
    "normal": {"hemoglobin": "138 g/L", "wbc": "7.2 x10^9/L", "creatinine": "85 umol/L", "crp": "3 mg/L"},
    "anemia": {"hemoglobin": "92 g/L", "mcv": "72 fL", "ferritin": "8 ng/mL", "crp": "5 mg/L"},
    "infection": {"wbc": "14.5 x10^9/L", "crp": "85 mg/L", "procalcitonin": "1.2 ng/mL", "creatinine": "90 umol/L"},
    "renal": {"creatinine": "320 umol/L", "urea": "18 mmol/L", "potassium": "5.8 mmol/L", "hemoglobin": "105 g/L"},
    "hepatic": {"alt": "180 U/L", "ast": "145 U/L", "bilirubin": "45 umol/L", "albumin": "28 g/L"},
    "cardiac": {"troponin": "850 ng/L", "bnp": "680 pg/mL", "creatinine": "95 umol/L", "hemoglobin": "130 g/L"},
    "thyroid": {"tsh": "0.02 mIU/L", "free_t4": "42 pmol/L", "hemoglobin": "125 g/L", "crp": "4 mg/L"},
    "coagulopathy": {"platelets": "45 x10^9/L", "inr": "2.8", "hemoglobin": "98 g/L", "wbc": "6.8 x10^9/L"},
    "dk": {"glucose": "28 mmol/L", "ph": "7.18", "bicarbonate": "12 mmol/L", "ketones": "4.2 mmol/L"},
}

IMAGING_PROFILES: dict[str, dict[str, str]] = {
    "none": {},
    "chest_xray_infiltrate": {"modality": "CXR", "finding": "Right lower lobe consolidation"},
    "chest_xray_cardiomegaly": {"modality": "CXR", "finding": "Cardiomegaly with pulmonary edema"},
    "ct_pe": {"modality": "CT-PA", "finding": "Segmental pulmonary embolism right lower lobe"},
    "ct_appendix": {"modality": "CT abdomen", "finding": "Enlarged appendix 11mm with periappendiceal fat stranding"},
    "mri_brain_stroke": {"modality": "MRI brain", "finding": "Acute left MCA territory infarct"},
    "us_renal_stone": {"modality": "Renal ultrasound", "finding": "7mm left ureteric calculus with hydronephrosis"},
    "us_obstetric": {"modality": "Obstetric ultrasound", "finding": "Single live intrauterine pregnancy 32 weeks"},
    "echo_reduced_ef": {"modality": "Echocardiography", "finding": "LVEF 35% with regional wall motion abnormality"},
}

ECG_PROFILES: dict[str, str] = {
    "none": "",
    "normal_sinus": "Normal sinus rhythm, rate 78/min",
    "st_elevation": "ST elevation V2-V4, reciprocal changes inferior leads",
    "atrial_fibrillation": "Atrial fibrillation, ventricular rate 110/min",
    "tachycardia": "Sinus tachycardia 125/min, no ST changes",
    "hyperkalemia": "Peaked T waves, widened QRS, sine wave pattern",
    "long_qt": "QTc 520ms, sinus rhythm",
}


def _pick(pool: tuple, idx: int) -> str:
    return pool[idx % len(pool)]


def _pick_many(pool: tuple, idx: int, count: int) -> list[str]:
    items: list[str] = []
    for i in range(count):
        item = _pick(pool, idx + i * 7)
        if item not in items:
            items.append(item)
    return items


def age_for_group(age_group: str, variant: int) -> int:
    if age_group == "pediatric":
        return 2 + (variant % 16)
    if age_group == "elderly":
        return 65 + (variant % 25)
    if age_group == "pregnancy":
        return 22 + (variant % 18)
    return 18 + (variant % 47)


def age_group_for(age: int, pregnancy: str) -> str:
    if pregnancy == "pregnant":
        return "pregnancy"
    if age < 18:
        return "pediatric"
    if age >= 65:
        return "elderly"
    return "adult"


@dataclass(frozen=True)
class ParameterSpace:
    """Dimensions multiplied to exceed 100k unique cases."""

    specialties: int
    seeds_per_specialty: int
    variants_per_seed: int

    @property
    def total_capacity(self) -> int:
        return self.specialties * self.seeds_per_specialty * self.variants_per_seed


def build_parameters(
    *,
    variant_index: int,
    age_group_hint: str,
    lab_key: str,
    imaging_key: str,
    ecg_key: str,
    requires_emergency: bool,
    rng_seed: int,
) -> CaseParameters:
    """Deterministic parameter tuple from variant index."""
    vi = variant_index
    sex = "female" if vi % 2 else "male"
    pregnancy = "none"
    if age_group_hint == "pregnancy" or (vi % 17 == 0 and sex == "female"):
        pregnancy = _pick(PREGNANCY_STATES, vi // 3)
    age = age_for_group(age_group_hint if pregnancy == "none" else "pregnancy", vi)
    severity = _pick(SEVERITY_LEVELS, vi // 5)
    progression = _pick(PROGRESSION_TYPES, vi // 11)
    chronic = _pick_many(CHRONIC_CONDITIONS, vi, 1 + (vi % 3))
    meds = _pick_many(MEDICATIONS, vi + 3, 1 + (vi % 2))
    occupation = _pick(OCCUPATIONS, vi // 7)
    risks = _pick_many(RISK_FACTORS, vi + 11, 1 + (vi % 2))
    comorbidities = _pick_many(CHRONIC_CONDITIONS, vi + 19, vi % 2)

    lab = dict(LAB_PROFILES.get(lab_key, LAB_PROFILES["normal"]))
    imaging = dict(IMAGING_PROFILES.get(imaging_key, {}))
    ecg = ECG_PROFILES.get(ecg_key, "")

    # Mix lab keys for additional uniqueness
    extra_lab = _pick(tuple(LAB_PROFILES.keys()), vi // 13)
    if extra_lab != lab_key and vi % 4 == 0:
        lab.update({k: v for k, v in list(LAB_PROFILES[extra_lab].items())[:2]})

    emergency = requires_emergency or severity == "critical"

    return CaseParameters(
        age=age,
        sex=sex,
        pregnancy_status=pregnancy,
        chronic_conditions=chronic,
        medications=meds,
        occupation=occupation,
        risk_factors=risks,
        symptom_combination=[],
        disease_severity=severity,
        laboratory_values=lab,
        imaging_findings=imaging,
        ecg_findings=ecg,
        comorbidities=comorbidities,
        disease_progression=progression,
        emergency_status=emergency,
        variant_index=variant_index,
    )


def case_fingerprint(specialty: str, seed_id: str, params: CaseParameters) -> str:
    """Stable hash for deduplication."""
    raw = f"{specialty}|{seed_id}|{params.age}|{params.sex}|{params.pregnancy_status}|{params.disease_severity}|{params.variant_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
