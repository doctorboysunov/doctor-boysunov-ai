"""Phone normalization for duplicate detection."""

from __future__ import annotations

import re


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.strip())
    if not digits:
        raise ValueError("Phone number is empty")

    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if phone.strip().startswith("+") and len(digits) >= 10:
        return f"+{digits}"

    raise ValueError(f"Unsupported phone format: {phone!r}")


def phones_equivalent(left: str, right: str) -> bool:
    try:
        return normalize_phone(left) == normalize_phone(right)
    except ValueError:
        return False
