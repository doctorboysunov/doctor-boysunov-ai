"""Phase 4 — Complaint Recognition & Dynamic Clinical Pathways."""

from app.clinical_brain.clinical_pathways.formatter import format_pathway_block, format_pathway_principles
from app.clinical_brain.clinical_pathways.recognition import recognize_pathway, resolve_complaint_category
from app.clinical_brain.clinical_pathways.registry import (
    all_pathways,
    default_pathway_for_category,
    get_pathway,
    register_pathway,
)
from app.clinical_brain.clinical_pathways.selector import apply_pathway_closure_gate, build_pathway_context
from app.clinical_brain.clinical_pathways.types import (
    PHASE_4_VERSION,
    ClinicalPathway,
    PathwayContext,
    PathwayNode,
)

__all__ = [
    "PHASE_4_VERSION",
    "ClinicalPathway",
    "PathwayContext",
    "PathwayNode",
    "all_pathways",
    "apply_pathway_closure_gate",
    "build_pathway_context",
    "default_pathway_for_category",
    "format_pathway_block",
    "format_pathway_principles",
    "get_pathway",
    "recognize_pathway",
    "register_pathway",
    "resolve_complaint_category",
]
