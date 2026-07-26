"""Log guideline disagreements for continuous improvement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evidence.types import EvidenceReport, GuidelineDisagreement, GuidelineRule

DISAGREEMENTS_JSONL = Path("data/training/evidence/disagreements.jsonl")
EVIDENCE_REPORTS_DIR = Path("data/training/evidence/reports")


def log_disagreements(
    report: EvidenceReport,
    rules: list[GuidelineRule],
    *,
    specialty: str,
) -> list[GuidelineDisagreement]:
    """Persist every guideline disagreement from an evidence report."""
    DISAGREEMENTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    records: list[GuidelineDisagreement] = []
    rule_by_source = {r.source: r for r in rules}

    def _append(disagreement_type: str, description: str, source: str, severity: str = "medium") -> None:
        rule = rule_by_source.get(source) or (rules[0] if rules else None)
        rec = GuidelineDisagreement(
            case_id=report.case_id,
            timestamp=ts,
            source=source,
            rule_id=rule.rule_id if rule else "unknown",
            disagreement_type=disagreement_type,
            description=description,
            gold_diagnosis=report.gold_diagnosis,
            specialty=specialty,
            severity=severity,
        )
        records.append(rec)
        with DISAGREEMENTS_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    for rf in report.missed_red_flags:
        src = rf.split("]")[0].strip("[") if "]" in rf else "WHO"
        _append("missed_red_flag", rf, src, "high")

    for inv in report.unnecessary_investigations:
        _append("unnecessary_investigation", inv, rules[0].source if rules else "Other", "low")

    for unsafe in report.unsafe_advice_risks:
        _append("unsafe_advice", unsafe, "WHO", "high")

    for dev in report.guideline_deviations:
        src = dev.split("]")[0].strip("[") if "]" in dev else "NICE"
        _append("guideline_deviation", dev, src, "medium")

    for conflict in report.conflicting_recommendations:
        _append("conflict", conflict, rules[0].source if rules else "Other", "high")

    for missing in report.missing_evidence[:5]:
        src = missing.split("]")[0].strip("[") if "]" in missing else "Other"
        _append("missing_evidence", missing, src, "medium")

    return records


def save_evidence_report(report: EvidenceReport) -> Path:
    EVIDENCE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_REPORTS_DIR / f"{report.case_id}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_disagreements(*, limit: int = 500) -> list[dict]:
    if not DISAGREEMENTS_JSONL.exists():
        return []
    lines = DISAGREEMENTS_JSONL.read_text(encoding="utf-8").splitlines()
    return [json.loads(ln) for ln in lines[-limit:] if ln.strip()]
