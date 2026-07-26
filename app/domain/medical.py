"""Universal Medical AI — specialty and routing domain types."""

from __future__ import annotations

from typing import Literal

MedicalSpecialty = Literal[
    "internal_medicine",
    "neurology",
    "cardiology",
    "pulmonology",
    "gastroenterology",
    "endocrinology",
    "nephrology",
    "rheumatology",
    "infectious_diseases",
    "hematology",
    "oncology",
    "general_surgery",
    "orthopedics",
    "urology",
    "gynecology",
    "obstetrics",
    "pediatrics",
    "dermatology",
    "ent",
    "ophthalmology",
    "psychiatry",
    "emergency_medicine",
    "intensive_care",
]

SPECIALTY_LABELS: dict[str, str] = {
    "internal_medicine": "Ichki kasalliklar",
    "neurology": "Nevrologiya",
    "cardiology": "Kardiologiya",
    "pulmonology": "Pulmonologiya",
    "gastroenterology": "Gastroenterologiya",
    "endocrinology": "Endokrinologiya",
    "nephrology": "Nefrologiya",
    "rheumatology": "Revmatologiya",
    "infectious_diseases": "Yuqumli kasalliklar",
    "hematology": "Gematologiya",
    "oncology": "Onkologiya",
    "general_surgery": "Umumiy jarrohlik",
    "orthopedics": "Ortopediya",
    "urology": "Urologiya",
    "gynecology": "Ginekologiya",
    "obstetrics": "Akusherlik",
    "pediatrics": "Pediatriya",
    "dermatology": "Dermatologiya",
    "ent": "LOR (quloq-burun-tomoq)",
    "ophthalmology": "Oftalmologiya",
    "psychiatry": "Psixiatriya",
    "emergency_medicine": "Shoshilinch yordam",
    "intensive_care": "Intensiv terapiya",
}

# World-class training target — 24 major clinical specialties
WORLD_CLASS_SPECIALTIES: tuple[MedicalSpecialty, ...] = (
    "internal_medicine",
    "neurology",
    "cardiology",
    "pulmonology",
    "gastroenterology",
    "endocrinology",
    "nephrology",
    "rheumatology",
    "infectious_diseases",
    "hematology",
    "oncology",
    "general_surgery",
    "orthopedics",
    "urology",
    "gynecology",
    "obstetrics",
    "pediatrics",
    "dermatology",
    "ent",
    "ophthalmology",
    "psychiatry",
    "emergency_medicine",
    "intensive_care",
)

ALL_SPECIALTIES: tuple[MedicalSpecialty, ...] = WORLD_CLASS_SPECIALTIES


def specialty_label(specialty: str) -> str:
    return SPECIALTY_LABELS.get(specialty, specialty)
