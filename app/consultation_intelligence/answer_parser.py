"""Parse patient answers into structured clinical values."""

from __future__ import annotations

import re

_NEGATIVE = frozenset({"yo'q", "yoq", "yok", "no", "none", "emas", "yo'q emas", " yoʻq", " yoʻq."})
_POSITIVE = frozenset({"ha", "yes", "bor", "ha bor", "albatta", "aynan"})

_SCREEN_SLUG_MARKERS = ("triage", "screen", "snoop", "red_flag", "cauda", "stroke", "central", "myelo")


def _is_screen_slug(topic_slug: str) -> bool:
    return any(m in topic_slug for m in _SCREEN_SLUG_MARKERS)


def _parse_screen_answer(topic_slug: str, lowered: str) -> str | None:
    if re.search(r"\byo['']?q\b|emas| yoʻq", lowered):
        return "negative"
    if "cauda" in topic_slug:
        if lowered in _NEGATIVE:
            return "negative"
        if re.search(r"kuchsiz|siydik|najas|sezgi|tutolmay|hojatxon|ikki", lowered):
            return "positive"
        if lowered in _POSITIVE:
            return "negative"
        return "negative"
    if "stroke" in topic_slug or "central" in topic_slug or "myelo" in topic_slug:
        if re.search(r"nutq|yuz|qo['']?l|gap|birdan|insult|ko['']?rish", lowered):
            return "positive"
        if lowered in _POSITIVE:
            return "negative"
        return "negative"
    if "snoop" in topic_slug:
        if re.search(r"birdan|eng kuchli|hush|isitma|nutq|ko['']?rish|kuchsiz", lowered):
            return "positive"
        if lowered in _POSITIVE:
            return "negative"
        return "negative"
    if lowered in _POSITIVE:
        return "positive"
    if lowered in _NEGATIVE:
        return "negative"
    if re.search(r"\bha\b|bor|aynan", lowered) and len(lowered.split()) <= 4:
        return "positive"
    return None


def parse_answer(topic_slug: str, raw: str) -> str:
    text = (raw or "").strip()
    lowered = text.lower()

    if _is_screen_slug(topic_slug):
        screen = _parse_screen_answer(topic_slug, lowered)
        if screen is not None:
            return screen

    if lowered in _NEGATIVE:
        return "negative"
    if lowered in _POSITIVE:
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
