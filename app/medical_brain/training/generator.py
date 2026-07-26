"""Combinatorial clinical case generator — 100,000+ unique cases."""

from __future__ import annotations

import re
from typing import Iterator

from app.domain.medical import WORLD_CLASS_SPECIALTIES
from app.medical_brain.evaluation.blind_clinical.types import BlindTurn
from app.medical_brain.training.parameters import (
    ParameterSpace,
    age_group_for,
    build_parameters,
    case_fingerprint,
)
from app.medical_brain.training.seeds.catalog import all_seeds
from app.medical_brain.training.types import (
    SEEDS_PER_SPECIALTY,
    VARIANTS_PER_SEED,
    GeneratedClinicalCase,
    TARGET_CASE_CAPACITY,
)

_SEX_UZ = {"male": "Erkak", "female": "Ayol"}
_PREG_UZ = {"none": "", "pregnant": "homilador", "postpartum": "tugruqdan keyin"}


def parameter_space() -> ParameterSpace:
    n_spec = len(WORLD_CLASS_SPECIALTIES)
    return ParameterSpace(
        specialties=n_spec,
        seeds_per_specialty=SEEDS_PER_SPECIALTY,
        variants_per_seed=VARIANTS_PER_SEED,
    )


def total_case_capacity() -> int:
    return parameter_space().total_capacity


def _decode_index(global_index: int) -> tuple[int, int, int]:
    """Map flat index → (specialty_idx, seed_idx, variant_idx)."""
    n_spec = len(WORLD_CLASS_SPECIALTIES)
    variants = VARIANTS_PER_SEED
    seeds = SEEDS_PER_SPECIALTY
    per_spec = seeds * variants
    spec_idx = global_index // per_spec
    rem = global_index % per_spec
    seed_idx = rem // variants
    variant_idx = rem % variants
    if spec_idx >= n_spec:
        raise IndexError(f"Index {global_index} exceeds capacity {total_case_capacity()}")
    return spec_idx % n_spec, seed_idx % seeds, variant_idx


def _render(template: str, params, age_group: str) -> str:
    d = str(3 + (params.variant_index % 58))
    t = str(round(37.0 + (params.variant_index % 40) * 0.1, 1))
    a = str(params.age)
    n = str(params.variant_index + 1)
    text = template.replace("{d}", d).replace("{t}", t).replace("{a}", a).replace("{n}", n)
    if params.chronic_conditions and params.variant_index % 3 == 0:
        text += f" ({params.chronic_conditions[0]} bor)"
    if params.medications and params.medications[0] != "no regular medications" and params.variant_index % 5 == 0:
        text += f", {params.medications[0]} ichaman"
    return text


def _build_profile(params, age_group: str) -> str:
    parts = [
        f"{_SEX_UZ.get(params.sex, params.sex)}, {params.age} yosh",
        f"kasb: {params.occupation}",
    ]
    preg = _PREG_UZ.get(params.pregnancy_status, "")
    if preg:
        parts.append(preg)
    if params.chronic_conditions:
        parts.append("surunkali: " + ", ".join(params.chronic_conditions[:2]))
    if params.medications:
        meds = [m for m in params.medications if m != "no regular medications"]
        if meds:
            parts.append("dori: " + ", ".join(meds[:2]))
    if params.risk_factors:
        parts.append("xavf: " + params.risk_factors[0])
    if params.laboratory_values and params.variant_index % 7 == 0:
        lab_snip = next(iter(params.laboratory_values.items()))
        parts.append(f"lab ({lab_snip[0]}: {lab_snip[1]})")
    if params.imaging_findings and params.variant_index % 11 == 0:
        parts.append(f"tasvir: {params.imaging_findings.get('finding', '')}")
    if params.ecg_findings and params.variant_index % 13 == 0:
        parts.append(f"EKG: {params.ecg_findings[:60]}")
    return "; ".join(parts)


def _age_group_for_seed(seed, params) -> str:
    cat = seed.category
    if cat in ("pediatric",):
        return "pediatric"
    if cat == "pregnancy":
        return "pregnancy"
    if params.age >= 65:
        return "elderly"
    if params.pregnancy_status == "pregnant":
        return "pregnancy"
    return age_group_for(params.age, params.pregnancy_status)


def generate_case(global_index: int) -> GeneratedClinicalCase:
    """Generate one unique case by deterministic global index."""
    spec_idx, seed_idx, variant_idx = _decode_index(global_index)
    specialty = WORLD_CLASS_SPECIALTIES[spec_idx]
    seeds = all_seeds()[specialty]
    seed = seeds[seed_idx % len(seeds)]

    age_hint = "adult"
    if seed.category == "pediatric":
        age_hint = "pediatric"
    elif seed.category == "pregnancy":
        age_hint = "pregnancy"
    elif seed.category == "elderly":
        age_hint = "elderly"

    params = build_parameters(
        variant_index=variant_idx + global_index * 31,
        age_group_hint=age_hint,
        lab_key=seed.lab_profile_key,
        imaging_key=seed.imaging_profile_key,
        ecg_key=seed.ecg_profile_key,
        requires_emergency=seed.requires_emergency,
        rng_seed=global_index,
    )
    age_group = _age_group_for_seed(seed, params)
    fp = case_fingerprint(specialty, seed.seed_id, params)
    case_id = f"wc_{specialty}_{global_index:06d}_{fp[:8]}"

    opener = _render(seed.opener_template, params, age_group)
    followup = _render(seed.followup_template, params, age_group)
    probe = seed.assistant_probe

    turns = [
        BlindTurn(role="user", content=opener),
        BlindTurn(role="assistant", content=probe),
        BlindTurn(role="user", content=followup),
    ]

    profile = _build_profile(params, age_group)
    emergency = seed.requires_emergency or params.emergency_status

    return GeneratedClinicalCase(
        id=case_id,
        specialty=specialty,
        category=seed.category,
        age_group=age_group,
        patient_profile=profile,
        turns=turns,
        parameters=params,
        gold_diagnosis=seed.gold_diagnosis,
        differential_diagnosis=list(seed.differential_diagnosis),
        red_flags=list(seed.red_flags),
        reasoning_steps=list(seed.reasoning_steps),
        expected_questions=list(seed.expected_questions),
        referral_decision=seed.referral_decision,
        urgency_level=seed.urgency_level if not emergency else "emergency",
        guideline_references=list(seed.guideline_references),
        expected_primary=specialty,
        expected_secondary=list(seed.expected_secondary),
        requires_emergency=emergency,
    )


def generate_cases(
    count: int | None = None,
    *,
    start_index: int = 0,
) -> Iterator[GeneratedClinicalCase]:
    """Stream generated cases. Default count = full capacity."""
    cap = total_case_capacity()
    n = min(count or cap, cap - start_index)
    seen: set[str] = set()
    for i in range(start_index, start_index + n):
        case = generate_case(i)
        fp = case_fingerprint(case.specialty, case.id, case.parameters)
        if fp in seen:
            continue
        seen.add(fp)
        yield case


def verify_capacity(minimum: int = TARGET_CASE_CAPACITY) -> bool:
    cap = total_case_capacity()
    return cap >= minimum
