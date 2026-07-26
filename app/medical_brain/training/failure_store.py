"""Persist and retrieve failed clinical cases for continuous learning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.training.failure_analysis import (
    classify_failure,
    root_cause_analysis,
    suggest_improvements,
)
from app.medical_brain.training.types import FailedCaseRecord, GeneratedClinicalCase, TrainingCaseResult

FAILURES_DIR = Path("data/training/failures")
FAILURES_JSONL = FAILURES_DIR / "failures.jsonl"
RECURRING_FILE = FAILURES_DIR / "recurring_failures.json"
CYCLE_COUNTER_FILE = Path("data/training/cycle_counter.txt")


def _next_cycle_id() -> int:
    CYCLE_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CYCLE_COUNTER_FILE.exists():
        n = int(CYCLE_COUNTER_FILE.read_text(encoding="utf-8").strip())
    else:
        n = 0
    return n + 1


def set_cycle_id(cycle_id: int) -> None:
    CYCLE_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    CYCLE_COUNTER_FILE.write_text(str(cycle_id), encoding="utf-8")


def get_current_cycle_id() -> int:
    if CYCLE_COUNTER_FILE.exists():
        return int(CYCLE_COUNTER_FILE.read_text(encoding="utf-8").strip())
    return 0


def save_failed_case(
    case: GeneratedClinicalCase,
    result: TrainingCaseResult,
    *,
    cycle_id: int,
    retry_count: int = 0,
) -> FailedCaseRecord:
    """Automatically persist every failed case with full analysis."""
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    categories = classify_failure(case, result)
    root_causes = root_cause_analysis(case, result, categories)
    suggestions = suggest_improvements(categories, case, result)

    record = FailedCaseRecord(
        case_id=case.id,
        cycle_id=cycle_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        specialty=case.specialty,
        category=case.category,
        gold_diagnosis=case.gold_diagnosis,
        failure_categories=categories,
        root_causes=root_causes,
        failure_reasons=result.failure_reasons,
        improvement_suggestions=suggestions,
        scores=result.scores.to_dict(),
        routing_primary=result.routing_primary,
        routing_secondary=result.routing_secondary,
        missed_red_flags=result.missed_red_flags,
        case_snapshot=case.to_dict(),
        retry_count=retry_count,
        resolved=False,
    )

    with FAILURES_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    result.failure_categories = categories
    result.root_causes = root_causes
    result.improvement_actions = suggestions

    return record


def load_all_failures(*, unresolved_only: bool = False) -> list[FailedCaseRecord]:
    if not FAILURES_JSONL.exists():
        return []
    records: list[FailedCaseRecord] = []
    for line in FAILURES_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        rec = FailedCaseRecord(**{k: data[k] for k in FailedCaseRecord.__dataclass_fields__ if k in data})
        if unresolved_only and rec.resolved:
            continue
        records.append(rec)
    return records


def load_case_snapshot(case_id: str) -> dict | None:
    for rec in reversed(load_all_failures()):
        if rec.case_id == case_id:
            return rec.case_snapshot
    return None


def mark_resolved(case_id: str, cycle_id: int) -> None:
    """Mark failures as resolved when re-evaluation passes."""
    if not FAILURES_JSONL.exists():
        return
    lines = []
    for line in FAILURES_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("case_id") == case_id and not data.get("resolved"):
            data["resolved"] = True
            data["resolved_cycle"] = cycle_id
        lines.append(json.dumps(data, ensure_ascii=False))
    FAILURES_JSONL.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def update_recurring_failures(case_ids: list[str]) -> list[str]:
    """Track case IDs that fail repeatedly across cycles."""
    RECURRING_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, int] = {}
    if RECURRING_FILE.exists():
        existing = json.loads(RECURRING_FILE.read_text(encoding="utf-8"))

    recurring: list[str] = []
    for cid in case_ids:
        existing[cid] = existing.get(cid, 0) + 1
        if existing[cid] >= 2:
            recurring.append(cid)

    RECURRING_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return recurring


def get_recurring_failure_ids(min_occurrences: int = 2) -> list[str]:
    if not RECURRING_FILE.exists():
        return []
    data = json.loads(RECURRING_FILE.read_text(encoding="utf-8"))
    return [cid for cid, n in data.items() if n >= min_occurrences]
