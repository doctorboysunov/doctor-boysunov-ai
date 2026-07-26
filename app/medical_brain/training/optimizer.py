"""Automatic prompt and routing improvement from failed training cases."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.medical_brain.training.types import PRODUCTION_QUALITY, TrainingCaseResult, TrainingReport, TrainingScores

PATCHES_FILE = Path("data/training/applied_patches.json")
SUGGESTIONS_FILE = Path("data/training/optimization_suggestions.json")


@dataclass
class OptimizationPatch:
    patch_id: str
    patch_type: str  # router | red_flag | prompt | coordination
    target: str
    pattern: str
    rationale: str
    source_failures: int = 0

    def to_dict(self) -> dict[str, str]:
        return {
            "patch_id": self.patch_id,
            "patch_type": self.patch_type,
            "target": self.target,
            "pattern": self.pattern,
            "rationale": self.rationale,
            "source_failures": str(self.source_failures),
        }


@dataclass
class FailureCluster:
    failure_type: str
    count: int
    specialties: list[str] = field(default_factory=list)
    sample_case_ids: list[str] = field(default_factory=list)
    suggested_patches: list[OptimizationPatch] = field(default_factory=list)


def _extract_keywords(text: str, min_len: int = 5) -> list[str]:
    words = re.findall(r"[\w']+", text.lower())
    return [w for w in words if len(w) >= min_len][:8]


def analyze_failures(results: list[TrainingCaseResult]) -> list[FailureCluster]:
    """Cluster failures by type and specialty for targeted improvement."""
    clusters: dict[str, FailureCluster] = {}

    for r in results:
        if r.passed:
            continue
        for reason in r.failure_reasons:
            key = reason.split("—")[0].split(":")[0].strip()[:60]
            if key not in clusters:
                clusters[key] = FailureCluster(failure_type=key, count=0)
            c = clusters[key]
            c.count += 1
            if r.specialty not in c.specialties:
                c.specialties.append(r.specialty)
            if len(c.sample_case_ids) < 5:
                c.sample_case_ids.append(r.case_id)

        if r.missed_red_flags:
            key = "Missed red flags"
            if key not in clusters:
                clusters[key] = FailureCluster(failure_type=key, count=0)
            clusters[key].count += len(r.missed_red_flags)

        if r.scores.specialty_routing < PRODUCTION_QUALITY["specialty_routing"]:
            key = "Specialty routing failure"
            if key not in clusters:
                clusters[key] = FailureCluster(failure_type=key, count=0)
            clusters[key].count += 1
            if r.specialty not in clusters[key].specialties:
                clusters[key].specialties.append(r.specialty)

    return sorted(clusters.values(), key=lambda c: -c.count)


def generate_patches(clusters: list[FailureCluster], results: list[TrainingCaseResult]) -> list[OptimizationPatch]:
    """Generate concrete optimization patches from failure clusters."""
    patches: list[OptimizationPatch] = []
    failed = [r for r in results if not r.passed]

    routing_fails = [r for r in failed if r.scores.specialty_routing < PRODUCTION_QUALITY["specialty_routing"]]
    by_spec: Counter[str] = Counter(r.specialty for r in routing_fails)
    for spec, count in by_spec.most_common(10):
        patches.append(OptimizationPatch(
            patch_id=f"router_{spec}_{count}",
            patch_type="router",
            target=spec,
            pattern=f"Strengthen {spec} pattern matching in router overrides",
            rationale=f"{count} routing failures for {spec} in training batch",
            source_failures=count,
        ))

    red_flag_fails = [r for r in failed if r.missed_red_flags]
    flag_counter: Counter[str] = Counter()
    for r in red_flag_fails:
        for f in r.missed_red_flags:
            flag_counter[f] += 1
    for flag, count in flag_counter.most_common(8):
        patches.append(OptimizationPatch(
            patch_id=f"redflag_{flag[:20]}_{count}",
            patch_type="red_flag",
            target="consultation_red_flags",
            pattern=f"Expand detection for: {flag}",
            rationale=f"Missed {count} times in training batch",
            source_failures=count,
        ))

    safety_fails = [r for r in failed if r.scores.patient_safety < PRODUCTION_QUALITY["safety"]]
    if safety_fails:
        patches.append(OptimizationPatch(
            patch_id="prompt_emergency_triage",
            patch_type="prompt",
            target="prompts.py",
            pattern="EMERGENCY PRESENTATION — prioritize stabilization and minimal critical questions",
            rationale=f"{len(safety_fails)} safety failures — reinforce emergency triage language",
            source_failures=len(safety_fails),
        ))

    coord_fails = [r for r in failed if any("secondar" in x.lower() for x in r.failure_reasons)]
    for r in coord_fails[:5]:
        patches.append(OptimizationPatch(
            patch_id=f"coord_{r.case_id[-12:]}",
            patch_type="coordination",
            target="router.py",
            pattern=f"Add secondary coordination for {r.specialty} + {r.routing_secondary}",
            rationale=r.failure_reasons[0] if r.failure_reasons else "Missing secondary",
            source_failures=1,
        ))

    reasoning_fails = [r for r in failed if r.scores.reasoning_accuracy < PRODUCTION_QUALITY["reasoning_accuracy"]]
    if reasoning_fails:
        patches.append(OptimizationPatch(
            patch_id="prompt_rerank_ddx",
            patch_type="prompt",
            target="prompts.py",
            pattern="RE-RANK differential diagnoses for THIS turn",
            rationale=f"{len(reasoning_fails)} cases below reasoning threshold — reinforce DDx re-ranking",
            source_failures=len(reasoning_fails),
        ))

    return patches[:25]


def apply_safe_patches(patches: list[OptimizationPatch]) -> list[str]:
    """Apply patches that are safe to auto-apply (logged, non-destructive).

    Router and red-flag patches are recorded for manual review;
    prompt reinforcements are already in baseline prompts.
    Returns list of applied patch IDs.
    """
    PATCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if PATCHES_FILE.exists():
        existing = json.loads(PATCHES_FILE.read_text(encoding="utf-8"))

    applied: list[str] = []
    seen_ids = {p["patch_id"] for p in existing}
    for patch in patches:
        if patch.patch_id in seen_ids:
            continue
        if patch.patch_type in ("prompt", "coordination", "router", "red_flag"):
            existing.append({**patch.to_dict(), "status": "recorded_for_review"})
            applied.append(patch.patch_id)

    PATCHES_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return applied


def save_suggestions(patches: list[OptimizationPatch], clusters: list[FailureCluster]) -> Path:
    SUGGESTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "patches": [p.to_dict() for p in patches],
        "clusters": [
            {
                "failure_type": c.failure_type,
                "count": c.count,
                "specialties": c.specialties,
                "sample_case_ids": c.sample_case_ids,
            }
            for c in clusters
        ],
    }
    SUGGESTIONS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return SUGGESTIONS_FILE


def aggregate_metrics(results: list[TrainingCaseResult]) -> TrainingScores:
    if not results:
        return TrainingScores()
    totals = TrainingScores()
    for r in results:
        for metric in totals.to_dict():
            if metric == "overall":
                continue
            setattr(totals, metric, getattr(totals, metric) + getattr(r.scores, metric))
    n = len(results)
    for metric in totals.to_dict():
        if metric == "overall":
            continue
        setattr(totals, metric, round(getattr(totals, metric) / n, 2))
    return totals


def check_production_ready(averages: TrainingScores) -> bool:
    return (
        averages.reasoning_accuracy >= PRODUCTION_QUALITY["reasoning_accuracy"]
        and averages.patient_safety >= PRODUCTION_QUALITY["safety"]
        and averages.specialty_routing >= PRODUCTION_QUALITY["specialty_routing"]
        and averages.red_flag_detection >= PRODUCTION_QUALITY["red_flag_detection"]
        and averages.overall >= PRODUCTION_QUALITY["overall"]
    )
