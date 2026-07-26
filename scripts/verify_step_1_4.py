#!/usr/bin/env python3
"""Phase 1 Step 4 — medical system prompt builder verification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.infrastructure.ai import build_medical_system_prompt  # noqa: E402
from app.infrastructure.ai.prompt_builder import MEDICAL_ASSISTANT_ROLE  # noqa: E402
from app.safety.instructions import build_safety_instructions  # noqa: E402
from app.safety.safety_layer import combine_instructions  # noqa: E402
from app.services.receptionist_instructions import build_receptionist_instructions  # noqa: E402


def main() -> int:
    safety = build_safety_instructions()
    receptionist = build_receptionist_instructions()

    patient_prompt = build_medical_system_prompt(
        profile_instructions="Known patient: Ali, age 35",
        conversation_mode="patient",
    )
    assert safety.splitlines()[0] in patient_prompt
    assert MEDICAL_ASSISTANT_ROLE.splitlines()[0] in patient_prompt
    assert "AI receptionist" in patient_prompt or receptionist.splitlines()[0][:20] in patient_prompt
    assert "Known patient: Ali, age 35" in patient_prompt

    admin_prompt = build_medical_system_prompt(
        profile_instructions="Admin context",
        conversation_mode="doctor_admin",
    )
    assert safety.splitlines()[0] in admin_prompt
    assert MEDICAL_ASSISTANT_ROLE.splitlines()[0] in admin_prompt
    assert "AI receptionist" not in admin_prompt
    assert "Admin context" in admin_prompt

    # Backward-compatible combine_instructions delegates to prompt builder
    patient_combined = combine_instructions(
        profile_instructions="PROFILE",
        receptionist_instructions=receptionist,
    )
    assert "PROFILE" in patient_combined
    assert "AI receptionist" in patient_combined or receptionist.splitlines()[0][:20] in patient_combined

    admin_combined = combine_instructions(
        profile_instructions=None,
        receptionist_instructions=None,
    )
    assert "AI receptionist" not in admin_combined

    # openai_service uses the canonical prompt builder
    import inspect

    from app.services import openai_service  # noqa: E402

    source = inspect.getsource(openai_service.ask_ai)
    assert "build_medical_system_prompt" in source

    print("Phase 1 Step 4 OK: medical system prompt builder wired into AI layer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
