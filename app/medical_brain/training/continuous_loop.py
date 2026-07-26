"""Continuous clinical learning loop — evaluate, save failures, retry, track improvement."""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone

from app.medical_brain.evidence.reporter import write_batch_summary
from app.medical_brain.training.dashboard import (
    append_cycle_history,
    build_dashboard,
    load_cycle_history,
    write_dashboard,
)
from app.medical_brain.training.evaluator import evaluate_batch, evaluate_training_case
from app.medical_brain.training.failure_analysis import aggregate_recurring_mistakes
from app.medical_brain.training.failure_store import (
    get_recurring_failure_ids,
    mark_resolved,
    save_failed_case,
    set_cycle_id,
    update_recurring_failures,
)
from app.medical_brain.training.generator import generate_case, total_case_capacity
from app.medical_brain.training.optimizer import (
    analyze_failures,
    apply_safe_patches,
    aggregate_metrics,
    generate_patches,
    save_suggestions,
)
from app.medical_brain.training.types import (
    ClinicalQualityDashboard,
    FailedCaseRecord,
    GeneratedClinicalCase,
    LearningCycleRecord,
    TrainingCaseResult,
)


def _case_from_snapshot(snapshot: dict) -> GeneratedClinicalCase:
    from app.medical_brain.evaluation.blind_clinical.types import BlindTurn
    from app.medical_brain.training.types import CaseParameters

    params_data = snapshot["parameters"]
    params = CaseParameters(
        age=params_data["age"],
        sex=params_data["sex"],
        pregnancy_status=params_data["pregnancy_status"],
        chronic_conditions=params_data["chronic_conditions"],
        medications=params_data["medications"],
        occupation=params_data["occupation"],
        risk_factors=params_data["risk_factors"],
        symptom_combination=params_data.get("symptom_combination", []),
        disease_severity=params_data["disease_severity"],
        laboratory_values=params_data["laboratory_values"],
        imaging_findings=params_data["imaging_findings"],
        ecg_findings=params_data["ecg_findings"],
        comorbidities=params_data["comorbidities"],
        disease_progression=params_data["disease_progression"],
        emergency_status=params_data["emergency_status"],
        variant_index=params_data.get("variant_index", 0),
    )
    turns = [BlindTurn(role=t["role"], content=t["content"]) for t in snapshot["turns"]]
    return GeneratedClinicalCase(
        id=snapshot["id"],
        specialty=snapshot["specialty"],
        category=snapshot["category"],
        age_group=snapshot["age_group"],
        patient_profile=snapshot["patient_profile"],
        turns=turns,
        parameters=params,
        gold_diagnosis=snapshot["gold_diagnosis"],
        differential_diagnosis=snapshot["differential_diagnosis"],
        red_flags=snapshot["red_flags"],
        reasoning_steps=snapshot["reasoning_steps"],
        expected_questions=snapshot["expected_questions"],
        referral_decision=snapshot["referral_decision"],
        urgency_level=snapshot["urgency_level"],
        guideline_references=snapshot["guideline_references"],
        expected_primary=snapshot["expected_primary"],
        expected_secondary=snapshot["expected_secondary"],
        requires_emergency=snapshot["requires_emergency"],
    )


def sample_case_indices(total: int, sample_size: int, seed: int = 42) -> list[int]:
    cap = total_case_capacity()
    n = min(sample_size, cap)
    rng = random.Random(seed)
    return sorted(rng.sample(range(cap), n))


def _by_specialty_stats(results: list[TrainingCaseResult]) -> dict[str, dict[str, float]]:
    by_spec: dict[str, dict[str, float]] = {}
    for r in results:
        if r.specialty not in by_spec:
            by_spec[r.specialty] = {"passed": 0, "failed": 0, "scores": []}
        if r.passed:
            by_spec[r.specialty]["passed"] += 1
        else:
            by_spec[r.specialty]["failed"] += 1
        by_spec[r.specialty]["scores"].append(r.scores.overall)

    for spec, data in by_spec.items():
        scores = data["scores"]
        data["avg_score"] = round(sum(scores) / len(scores), 2) if scores else 0
        total = data["passed"] + data["failed"]
        data["pass_rate"] = round(100 * data["passed"] / total, 1) if total else 0
        del data["scores"]
    return by_spec


def _avg_questions(results: list[TrainingCaseResult]) -> float:
    if not results:
        return 1.0
    return round(sum(r.question_count for r in results) / len(results), 2)


def retry_failed_cases(
    failed_records: list[FailedCaseRecord],
    *,
    cycle_id: int,
    max_retries: int = 5,
) -> tuple[list[TrainingCaseResult], list[str]]:
    """Re-run failed cases until they pass or max retries exhausted."""
    retried: list[TrainingCaseResult] = []
    still_failing: list[str] = []

    for rec in failed_records:
        if rec.retry_count >= max_retries:
            still_failing.append(rec.case_id)
            continue
        case = _case_from_snapshot(rec.case_snapshot)
        result = evaluate_training_case(case)
        retried.append(result)

        if result.passed:
            mark_resolved(rec.case_id, cycle_id)
        else:
            save_failed_case(case, result, cycle_id=cycle_id, retry_count=rec.retry_count + 1)
            still_failing.append(rec.case_id)

    return retried, still_failing


def run_continuous_learning_cycle(
    *,
    sample_size: int = 2000,
    seed: int = 42,
    max_retries: int = 5,
    cycle_id: int | None = None,
) -> tuple[LearningCycleRecord, ClinicalQualityDashboard]:
    """Full continuous learning cycle with failure persistence and dashboard update."""
    prior_cycles = load_cycle_history()
    cid = cycle_id if cycle_id is not None else (prior_cycles[-1].cycle_id + 1 if prior_cycles else 1)
    set_cycle_id(cid)

    cap = total_case_capacity()
    indices = sample_case_indices(cap, sample_size, seed)
    cases = [generate_case(i) for i in indices]
    results = evaluate_batch(cases)

    # Phase 2.2 — evidence-based guideline validation (internal only)
    from app.medical_brain.evidence.validate_case import validate_batch_evidence

    evidence_reports = validate_batch_evidence(cases, results)
    for r, ev in zip(results, evidence_reports):
        r.evidence_agreement = ev.agreement_score
        r.evidence_passed = ev.passed

    failure_records: list[FailedCaseRecord] = []
    failed_ids: list[str] = []
    for case, result in zip(cases, results):
        if not result.passed:
            rec = save_failed_case(case, result, cycle_id=cid)
            failure_records.append(rec)
            failed_ids.append(case.id)

    recurring = update_recurring_failures(failed_ids)

    # Optimization from failure patterns
    clusters = analyze_failures(results)
    patches = generate_patches(clusters, results)
    applied = apply_safe_patches(patches)
    save_suggestions(patches, clusters)

    # Retry failed cases until pass or max retries
    still_failing = failed_ids
    if failure_records:
        _, still_failing = retry_failed_cases(failure_records, cycle_id=cid, max_retries=max_retries)

    # Re-blind recurring failures from prior cycles (req #8)
    prior_recurring = get_recurring_failure_ids(min_occurrences=2)
    for rid in prior_recurring:
        from app.medical_brain.training.failure_store import load_case_snapshot

        snap = load_case_snapshot(rid)
        if not snap:
            continue
        case = _case_from_snapshot(snap)
        result = evaluate_training_case(case)
        if not result.passed:
            still_failing.append(rid)
            save_failed_case(case, result, cycle_id=cid, retry_count=1)

    passed = sum(1 for r in results if r.passed)
    averages = aggregate_metrics(results)
    prior_safety = prior_cycles[-1].metrics.get("patient_safety", averages.patient_safety) if prior_cycles else averages.patient_safety
    safety_delta = round(averages.patient_safety - prior_safety, 2)

    all_failures = aggregate_recurring_mistakes(failure_records)
    cat_counter: Counter[str] = Counter()
    for r in results:
        if not r.passed:
            for c in r.failure_categories:
                cat_counter[c] += 1
    top_mistakes = cat_counter.most_common(10) or all_failures

    # Optimization complete only when no recurring failures remain AND safety did not regress
    optimization_complete = (
        len(still_failing) == 0
        and len(recurring) == 0
        and safety_delta >= 0
    )

    cycle = LearningCycleRecord(
        cycle_id=cid,
        timestamp=datetime.now(timezone.utc).isoformat(),
        evaluated=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=round(100 * passed / len(results), 2) if results else 0,
        metrics=averages.to_dict(),
        avg_questions=_avg_questions(results),
        by_specialty=_by_specialty_stats(results),
        top_mistakes=top_mistakes,
        patches_applied=applied,
        recurring_failures=list(dict.fromkeys(still_failing))[:20],
        safety_delta=safety_delta,
        optimization_complete=optimization_complete,
    )

    append_cycle_history(cycle)
    dashboard = build_dashboard(cycle, results, failure_records, prior_cycles)
    dashboard.evidence_pass_rate = round(
        100 * sum(1 for e in evidence_reports if e.passed) / len(evidence_reports), 2
    ) if evidence_reports else 0.0
    dashboard.avg_evidence_agreement = round(
        sum(e.agreement_score for e in evidence_reports) / len(evidence_reports), 2
    ) if evidence_reports else 0.0
    write_dashboard(dashboard, cycle)
    write_batch_summary(evidence_reports)

    return cycle, dashboard
