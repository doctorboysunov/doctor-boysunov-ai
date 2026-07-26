"""Phase 4 — Complaint Recognition & Dynamic Clinical Pathways verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_phase_4_pathways.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["TELEGRAM_BOT_TOKEN"] = "phase4-pathways-test"
os.environ["OPENAI_API_KEY"] = "phase4-pathways-test"

sys.path.insert(0, str(ROOT))

from app.clinical_brain.clinical_pathways import (  # noqa: E402
    PHASE_4_VERSION,
    all_pathways,
    build_pathway_context,
    format_pathway_block,
    get_pathway,
    recognize_pathway,
    register_pathway,
    resolve_complaint_category,
)
from app.clinical_brain.clinical_pathways.types import ClinicalPathway, PathwayNode  # noqa: E402
from app.clinical_brain.prompts import build_clinical_brain_instructions  # noqa: E402
from app.clinical_brain.types import ClinicalBrainInput  # noqa: E402
from app.medical_brain.engine import build_medical_brain_input  # noqa: E402
from app.medical_brain.prompts import build_medical_brain_instructions  # noqa: E402


class TestRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append((name, detail or "failed"))


def main() -> None:
    runner = TestRunner()

    runner.check("phase4_version", PHASE_4_VERSION == "4.0.0", PHASE_4_VERSION)
    runner.check("registry_count", len(all_pathways()) >= 10, str(len(all_pathways())))

    cases = [
        ("Chap oyoq og'riyapti", "lumbar_radiculopathy"),
        ("Belim og'riyapti", "lumbar_spine"),
        ("Bo'ynim og'riyapti", "cervical_spine"),
        ("Boshim og'riyapti", "headache"),
        ("Bosh aylanmoqda", "vestibular"),
        ("Yuz qiyshayapti", "bell_palsy"),
        ("Qo'lim uyuq", "peripheral_neuropathy"),
        ("Bo'yin og'rig'i va qo'l uyuqligi", "cervical_radiculopathy"),
        ("Qo'lim titrayapti", "parkinsonian"),
        ("Tutqanoq bo'ldi", "epilepsy"),
        ("Nutqim buzildi, qo'lim ishlamay qoldi", "stroke_acute"),
    ]
    for text, expected in cases:
        pid, conf, _ = recognize_pathway(text)
        runner.check(f"recognize_{expected}", pid == expected, f"{text} -> {pid} ({conf})")

    runner.check(
        "not_other_neurological",
        resolve_complaint_category("Chap oyoq og'riyapti") != "other_neurological",
        resolve_complaint_category("Chap oyoq og'riyapti"),
    )

    ctx = build_pathway_context(
        message="Chap oyoq og'riyapti",
        topics_covered=[],
        category_hint="other_neurological",
    )
    runner.check("pathway_activated", ctx.pathway_id == "lumbar_radiculopathy", ctx.pathway_id)
    runner.check("syndrome_set", "radiculopathy" in ctx.syndrome.lower(), ctx.syndrome)
    runner.check("first_node", ctx.current_node is not None, "")
    runner.check("not_ready_early", not ctx.ready_for_closure, "")

    block = format_pathway_block(ctx)
    runner.check("prompt_has_pathway", "DYNAMIC CLINICAL PATHWAY" in block, "")
    runner.check("prompt_has_next_question", ctx.current_node and ctx.current_node.topic_slug in block, "")

    ctx_partial = build_pathway_context(
        message="Chap oyoq og'riyapti",
        topics_covered=["lumbar_rad_cauda_screen", "lumbar_rad_onset", "lumbar_rad_radiation"],
        category_hint="low_back_pain",
        known_facts={"clinical_pathway_id": "lumbar_radiculopathy"},
    )
    runner.check("progress_tracked", ctx_partial.completion_pct > 0, str(ctx_partial.completion_pct))
    runner.check("next_depends_on_prior", ctx_partial.current_node is not None, "")
    if ctx_partial.current_node:
        runner.check(
            "depends_on_prior_topics",
            bool(ctx_partial.current_node.depends_on),
            ctx_partial.current_node.depends_on,
        )

    brain_input = ClinicalBrainInput(
        patient_id=1,
        user_message="Chap oyoq og'riyapti",
        complaint_category="low_back_pain",
        session_messages=[{"role": "user", "content": "Chap oyoq og'riyapti"}],
    )
    instructions = build_clinical_brain_instructions(
        brain_input,
        memory={"memory_summary": "none", "known_facts": {}, "topics_covered": [], "prior_complaints": [], "conversation_lines": []},
        knowledge_reference="topics",
        detected_red_flags=[],
    )
    runner.check("clinical_prompt_pathway", "DYNAMIC CLINICAL PATHWAY" in instructions, "")
    runner.check("clinical_prompt_not_generic", "NOT generic" in instructions, "")

    med_input = build_medical_brain_input(
        patient_id=1,
        user_message="Chap oyoq og'riyapti",
        session_messages=[{"role": "user", "content": "Chap oyoq og'riyapti"}],
        known_facts={},
        topics_covered=[],
        prior_complaints=[],
        primary_specialty="neurology",
    )
    runner.check("medical_category_resolved", med_input.complaint_category == "low_back_pain", med_input.complaint_category)
    med_instructions = build_medical_brain_instructions(
        med_input,
        memory={"memory_summary": "none", "known_facts": {}, "topics_covered": [], "prior_complaints": [], "conversation_lines": []},
        detected_red_flags=[],
    )
    runner.check("medical_prompt_pathway", "lumbar_radiculopathy" in med_instructions, "")

    custom = ClinicalPathway(
        id="test_expandable",
        syndrome="Test syndrome",
        syndrome_label_uz="Test sindrom",
        base_category="headache",
        description_uz="Test",
        recognition_keywords=("test_keyword",),
        nodes=(PathwayNode("t1", "test_topic", "triage", "Test question?"),),
        min_required_topics=1,
    )
    register_pathway(custom)
    pid, _, _ = recognize_pathway("test_keyword signal")
    runner.check("expandable_register", pid == "test_expandable", pid)

    print()
    print("=" * 72)
    print(f"PHASE 4 PATHWAYS VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Phase 4 Complaint Recognition & Dynamic Clinical Pathways OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
