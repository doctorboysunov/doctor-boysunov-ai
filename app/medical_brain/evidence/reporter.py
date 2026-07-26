"""Internal evidence report generation — never patient-facing."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.medical_brain.evidence.disagreement_log import load_disagreements
from app.medical_brain.evidence.types import EvidenceReport

SUMMARY_JSON = Path("data/training/evidence/evidence_summary.json")
SUMMARY_MD = Path("data/training/evidence/evidence_validation_report.md")


def write_batch_summary(reports: list[EvidenceReport]) -> tuple[Path, Path]:
    """Write aggregate evidence validation summary."""
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    if not reports:
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "evaluated": 0}
        SUMMARY_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return SUMMARY_JSON, SUMMARY_MD

    avg_agreement = round(sum(r.agreement_score for r in reports) / len(reports), 2)
    passed = sum(1 for r in reports if r.passed)
    conf = Counter(r.confidence_level for r in reports)
    all_disagreements = load_disagreements(limit=2000)
    by_type = Counter(d.get("disagreement_type", "") for d in all_disagreements)
    by_source = Counter(d.get("source", "") for d in all_disagreements)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evaluated": len(reports),
        "evidence_pass_rate": round(100 * passed / len(reports), 2),
        "avg_agreement_score": avg_agreement,
        "confidence_distribution": dict(conf),
        "disagreements_by_type": dict(by_type.most_common(10)),
        "disagreements_by_source": dict(by_source.most_common(10)),
        "failed_cases": [r.case_id for r in reports if not r.passed][:30],
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Evidence-Based Clinical Validation Report",
        "",
        f"**Generated:** {payload['timestamp']}",
        f"**Cases validated:** {len(reports)}",
        f"**Evidence pass rate:** {payload['evidence_pass_rate']}%",
        f"**Average agreement score:** {avg_agreement}%",
        "",
        "> Internal report only — never shown to patients.",
        "",
        "## Confidence Distribution",
        "",
    ]
    for level, count in conf.items():
        lines.append(f"- {level}: {count}")

    lines.extend(["", "## Disagreements by Guideline Source", ""])
    for src, count in by_source.most_common(10):
        lines.append(f"- **{src}:** {count}")

    lines.extend(["", "## Disagreements by Type", ""])
    for dtype, count in by_type.most_common(10):
        lines.append(f"- {dtype}: {count}")

    if payload["failed_cases"]:
        lines.extend(["", "## Cases Below Evidence Threshold (sample)", ""])
        for cid in payload["failed_cases"][:15]:
            r = next((x for x in reports if x.case_id == cid), None)
            if r:
                lines.append(f"- **{cid}** ({r.gold_diagnosis}): agreement {r.agreement_score}%, confidence {r.confidence_level}")
                if r.missing_evidence:
                    lines.append(f"  - Missing: {r.missing_evidence[0][:100]}")

    lines.extend(["", "---", "*Logged disagreements: data/training/evidence/disagreements.jsonl*"])
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    return SUMMARY_JSON, SUMMARY_MD
