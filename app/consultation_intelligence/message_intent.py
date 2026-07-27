"""Patient message intent helpers — advice vs clinical answers."""

from __future__ import annotations

_ADVICE_PATTERNS: tuple[str, ...] = (
    "nima qilsam",
    "nima qilay",
    "nima qilish",
    "nima qilaman",
    "nima maslahat",
    "maslahat berasan",
    "qanday qilaman",
    "qanday qilish",
    "qanday davolansam",
    "maslahat bering",
    "maslahat kerak",
    "yordam bering",
    "what should i do",
    "what do i do",
    "ne qilish kerak",
    "ne qilsam",
)


def is_advice_question(text: str) -> bool:
    """True when patient asks what to do — not a clinical answer or menu selection."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(p in lowered for p in _ADVICE_PATTERNS)
