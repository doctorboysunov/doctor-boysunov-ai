"""Medical Brain V1 — frozen pipeline contract.

Changes require version bump and full evaluation re-run.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.1.0"
PHASE_3_NEUROLOGIST = "3.1.0"
PHASE_4_PATHWAYS = "4.0.0"

PIPELINE_STEPS = (
    "step0_specialty_coordination",
    "step1_patient_meaning",
    "step2_memory_summary",
    "step3_hypotheses",
    "step4_red_flags",
    "step4_emergency_assessment",
    "step5_missing_information",
    "step6_interview_phase",
    "step6_next_question_topic",
    "step6_next_question_rationale",
    "step6_alternatives_rejected",
    "step6_clinical_confidence",
    "step7_stop_asking",
    "step7_ready_for_summary",
)

REQUIRED_OUTPUT_FIELDS = (
    "patient_reply",
    "medical_brain",
    "doctor_emr",
    "known_facts",
    "topics_covered",
)

EMERGENCY_LEVELS = ("none", "routine", "urgent", "emergency")
CONFIDENCE_LEVELS = ("low", "medium", "high")
INTERVIEW_PHASES = ("triage", "narrative", "discriminator", "context", "closure")

MAX_PATIENT_REPLY_SENTENCES = 4
MAX_QUESTIONS_PER_TURN = 1
