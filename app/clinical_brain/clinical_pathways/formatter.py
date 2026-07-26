"""Format active clinical pathway for GPT instructions."""

from __future__ import annotations

from app.clinical_brain.clinical_pathways.registry import get_pathway
from app.clinical_brain.clinical_pathways.types import PathwayContext


def format_pathway_block(ctx: PathwayContext) -> str:
    """Inject disease-specific dynamic pathway into neurologist prompt."""
    pathway = get_pathway(ctx.pathway_id)
    if not pathway:
        return ""

    lines = [
        "COMPLAINT RECOGNITION & DYNAMIC CLINICAL PATHWAY (Phase 4):",
        f"• Active pathway: {pathway.id} — {ctx.syndrome_label_uz}",
        f"• Neurological syndrome: {ctx.syndrome} (NOT generic 'other neurological complaint')",
        f"• Recognition confidence: {ctx.recognition_confidence} — {ctx.recognition_rationale}",
    ]

    if pathway.triage_must_not_miss:
        lines.append(f"• Pathway must-not-miss: {pathway.triage_must_not_miss}")

    lines.extend([
        f"• Pathway progress: {len(ctx.completed_topics)}/{ctx.total_required} required topics "
        f"({ctx.completion_pct:.0f}% complete)",
    ])

    if ctx.completed_topics:
        lines.append(f"• Completed topics: {', '.join(ctx.completed_topics[:8])}")

    if ctx.pending_required_topics:
        lines.append(f"• Pending required: {', '.join(ctx.pending_required_topics[:6])}")

    if ctx.current_node:
        node = ctx.current_node
        lines.extend([
            "",
            "NEXT DISEASE-SPECIFIC QUESTION (mandatory focus this turn):",
            f"• Topic slug (record in topics_covered): {node.topic_slug}",
            f"• Phase: {node.phase}",
            f"• Ask about: {node.question_focus}",
        ])
        if node.depends_on:
            lines.append(f"• Builds on prior answers: {', '.join(node.depends_on)}")
        if node.rationale:
            lines.append(f"• Clinical rationale: {node.rationale}")
        lines.append(
            "• Adapt wording naturally to patient's prior answers — "
            "this is NOT a fixed script; next question MUST depend on what they already said."
        )
    else:
        lines.append("• All pathway nodes addressed — review for closure readiness.")

    if ctx.ready_for_closure:
        lines.append(
            "• Pathway completion criteria MET — you MAY set step7_ready_for_summary=true "
            "if clinical confidence is adequate."
        )
    else:
        lines.append(
            f"• DO NOT set step7_ready_for_summary=true until pathway complete "
            f"(minimum {pathway.min_required_topics} required topics including triage). "
            "Continue with the next disease-specific question."
        )

    return "\n".join(lines)


def format_pathway_principles() -> str:
    return """PHASE 4 — CLINICAL PATHWAY RULES:
• Immediately classify the dominant complaint into a specific neurological syndrome — never default to generic questioning.
• Activate the matching clinical pathway and ask disease-specific questions only.
• Each next question MUST logically follow from the patient's previous answer.
• Never repeat topics already in topics_covered or known_facts.
• Do not close the consultation until the active pathway has collected enough clinical information."""
