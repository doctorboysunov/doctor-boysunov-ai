"""Parse patient answers into structured clinical values."""

from __future__ import annotations

import re

_NEGATIVE = frozenset({"yo'q", "yoq", "yok", "no", "none", "emas", "yo'q emas", " yoʻq", " yoʻq."})
_POSITIVE = frozenset({"ha", "yes", "bor", "ha bor", "albatta", "aynan"})


def parse_answer(topic_slug: str, raw: str) -> str:
    text = (raw or "").strip()
    lowered = text.lower()
    if lowered in _NEGATIVE:
        return "negative"
    if lowered in _POSITIVE:
        return "positive"
    if "triage" in topic_slug or "screen" in topic_slug or "snoop" in topic_slug or "red_flag" in topic_slug:
        if re.search(r"\byo['']?q\b|emas| yoʻq", lowered):
            return "negative"
        if lowered in _POSITIVE:
            return "positive"
        if lowered in _NEGATIVE:
            return "negative"
        if "cauda" in topic_slug:
            if re.search(r"kuchsiz|siydik|najas|sezgi|tutolmay|hojatxon", lowered):
                return "positive"
            return "negative"
        if re.search(r"\bha\b|bor|aynan", lowered) and len(lowered.split()) <= 4:
            return "positive"
    if "onset" in topic_slug:
        if any(w in lowered for w in ("birdan", "to'satdan", "sudden", "acutely")):
            return "sudden_onset"
        if any(w in lowered for w in ("asta", "sekin", "gradual", "slowly")):
            return "gradual_onset"
    return text[:500]


def is_negative(parsed: str) -> bool:
    return parsed == "negative"


def is_positive(parsed: str) -> bool:
    return parsed == "positive"
