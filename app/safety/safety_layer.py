"""Central safety layer — every AI response must pass through here."""

from __future__ import annotations

from typing import Any

from app.safety.instructions import build_safety_instructions
from app.safety.red_flags import build_emergency_response, detect_red_flags
from app.safety.response_filter import sanitize_ai_response

# Test hook: incremented on every enforce_safety call to prove bypass is impossible.
_enforcement_count = 0


def get_enforcement_count() -> int:
    return _enforcement_count


def reset_enforcement_count() -> None:
    global _enforcement_count
    _enforcement_count = 0


def combine_instructions(
    *,
    profile_instructions: str | None,
) -> str:
    parts = [build_safety_instructions()]
    if profile_instructions:
        parts.append(profile_instructions)
    return "\n\n".join(parts)


def enforce_safety(*, user_message: str, ai_response: str) -> tuple[str, dict[str, Any]]:
    global _enforcement_count
    _enforcement_count += 1

    red_flags = detect_red_flags(user_message)
    if red_flags:
        return build_emergency_response(red_flags), {
            "action": "emergency",
            "red_flags": red_flags,
            "violations": [],
            "bypassed_ai": True,
        }

    safe_text, violations = sanitize_ai_response(user_message, ai_response)
    action = "allow" if not violations else "rewrite"
    return safe_text, {
        "action": action,
        "red_flags": [],
        "violations": violations,
        "bypassed_ai": False,
    }


def extract_latest_user_message(history: list[dict[str, str]] | str) -> str:
    if isinstance(history, str):
        return history
    for message in reversed(history):
        if message.get("role") == "user" and message.get("content"):
            return message["content"]
    if history:
        return history[-1].get("content", "")
    return ""
