"""Attach engine improvement recommendations to challenge report."""

from __future__ import annotations

from app.medical_brain.evaluation.clinical_challenge.types import (
    ChallengeCaseResult,
    ChallengeReport,
)


def attach_improvements(report: ChallengeReport, results: list[ChallengeCaseResult]) -> ChallengeReport:
    if report.passed_suite:
        report.engine_improvements = [
            "Clinical Challenge passed — Medical Brain handles realistic multi-turn conversations safely.",
        ]
        return report

    actions: list[str] = []
    failed = [r for r in results if not r.passed]
    routing_fails = [r for r in failed if not r.checks.get("specialty_routing")]
    red_flag_fails = [r for r in failed if r.missed_red_flags]

    if routing_fails:
        specs = sorted({r.specialty for r in routing_fails})
        actions.append(f"Router: fix specialty patterns for {', '.join(specs[:5])}")
    if red_flag_fails:
        flags = sorted({f for r in red_flag_fails for f in r.missed_red_flags})
        actions.append(f"Red flags: add detection for {', '.join(flags[:5])}")

    for r in sorted(failed, key=lambda x: x.scores.overall)[:10]:
        if r.improvement_actions:
            actions.extend(r.improvement_actions[:1])

    report.engine_improvements = list(dict.fromkeys(actions))[:15]
    return report
