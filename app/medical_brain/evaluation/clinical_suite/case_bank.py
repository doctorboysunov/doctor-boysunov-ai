"""Build exactly 500 clinical evaluation cases."""

from __future__ import annotations

from app.medical_brain.evaluation.clinical_suite.case_templates import (
    CASES_PER_SPECIALTY,
    SPECIALTY_ORDER,
    _ANCHOR_CASES,
    _TEMPLATES,
)
from app.medical_brain.evaluation.clinical_suite.types import ClinicalCase

TARGET_TOTAL = 500


def _seed_to_case(
    specialty: str,
    idx: int,
    suffix: str,
    title: str,
    message: str,
    expected_primary: str,
    opts: dict,
    *,
    variant: int = 0,
) -> ClinicalCase:
    case_id = f"{idx:03d}_{specialty}_{suffix}" + (f"_v{variant}" if variant else "")
    return ClinicalCase(
        id=case_id,
        specialty=specialty,
        title=title if variant == 0 else f"{title} (variant {variant})",
        opening_message=message,
        expected_primary=expected_primary,
        expected_secondary=list(opts.get("expected_secondary", [])),
        expected_reasoning=opts.get("expected_reasoning", ""),
        expected_red_flags=list(opts.get("expected_red_flags", [])),
        forbidden_questions=list(opts.get("forbidden_questions", [])),
        expected_differentials=list(opts.get("expected_differentials", [])),
        expected_referral=opts.get("expected_referral", ""),
        requires_emergency=bool(opts.get("requires_emergency", False)),
        requires_multi_specialty=bool(opts.get("requires_multi_specialty", False)),
        expert_priority_phase=opts.get("expert_priority_phase", "narrative"),
        common_ai_mistake=opts.get("common_ai_mistake", "Generic template questioning"),
        improvement_hint=opts.get("improvement_hint", "Follow expert reasoning priority for this presentation"),
    )


def _expand_specialty(specialty: str, start_idx: int) -> list[ClinicalCase]:
    templates = _TEMPLATES.get(specialty, [])
    if not templates:
        return []
    cases: list[ClinicalCase] = []
    n = 0
    t_idx = 0
    while len(cases) < CASES_PER_SPECIALTY:
        suffix, title, message, primary, opts = templates[t_idx % len(templates)]
        variant = n // len(templates)
        cases.append(
            _seed_to_case(
                specialty,
                start_idx + len(cases),
                suffix,
                title,
                message,
                primary,
                opts,
                variant=variant,
            )
        )
        t_idx += 1
        n += 1
    return cases


def build_case_bank() -> tuple[ClinicalCase, ...]:
    all_cases: list[ClinicalCase] = []
    idx = 1
    for specialty in SPECIALTY_ORDER:
        batch = _expand_specialty(specialty, idx)
        all_cases.extend(batch)
        idx += len(batch)

    anchor_start = idx
    for i, (suffix, title, message, primary, opts) in enumerate(_ANCHOR_CASES):
        all_cases.append(
            _seed_to_case("multi_specialty", anchor_start + i, suffix, title, message, primary, opts)
        )

    return tuple(all_cases[:TARGET_TOTAL])


CLINICAL_CASES_500: tuple[ClinicalCase, ...] = build_case_bank()

assert len(CLINICAL_CASES_500) == TARGET_TOTAL, f"Expected {TARGET_TOTAL}, got {len(CLINICAL_CASES_500)}"
