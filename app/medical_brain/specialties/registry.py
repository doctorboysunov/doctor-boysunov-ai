"""Specialty module registry — lookup and reference block assembly."""

from __future__ import annotations

from app.domain.medical import MedicalSpecialty
from app.medical_brain.specialties.base import SpecialtyModule
from app.medical_brain.specialties.definitions import SPECIALTY_DEFINITIONS

_REGISTRY: dict[MedicalSpecialty, SpecialtyModule] = {
    module.id: module for module in SPECIALTY_DEFINITIONS
}


def get_specialty(specialty_id: MedicalSpecialty) -> SpecialtyModule | None:
    return _REGISTRY.get(specialty_id)


def get_all_specialties() -> tuple[SpecialtyModule, ...]:
    return SPECIALTY_DEFINITIONS


def format_multi_specialty_block(
    primary: MedicalSpecialty,
    secondary: list[MedicalSpecialty],
) -> str:
    """Build combined reference for coordinating specialties."""
    ids = [primary, *secondary]
    seen: set[str] = set()
    blocks: list[str] = []
    for sid in ids:
        if sid in seen:
            continue
        seen.add(sid)
        module = get_specialty(sid)
        if module:
            blocks.append(module.format_reference_block())

    if len(ids) > 1:
        labels = [get_specialty(s).label if get_specialty(s) else s for s in ids]
        header = (
            "MULTI-SPECIALTY COORDINATION (reason across all relevant specialties — NOT separate scripts):\n"
            f"Active specialties: {' + '.join(labels)}\n"
            "Integrate differentials and ask ONE question that serves the combined picture.\n"
        )
        return header + "\n\n".join(blocks)

    return "\n\n".join(blocks) if blocks else ""
