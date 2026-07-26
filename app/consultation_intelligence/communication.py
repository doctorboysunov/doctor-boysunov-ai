"""Template-based patient communication — no GPT for question selection."""

from __future__ import annotations

_ACKNOWLEDGMENTS = (
    "Tushundim.",
    "Rahmat, aytdiklaringizni inobatga oldim.",
    "Ma'lumot uchun rahmat.",
    "Eshitdim.",
)


def _pick_acknowledgment(turn: int) -> str:
    return _ACKNOWLEDGMENTS[turn % len(_ACKNOWLEDGMENTS)]


def _short_echo(user_message: str, max_words: int = 8) -> str:
    words = user_message.strip().split()
    if not words:
        return ""
    snippet = " ".join(words[:max_words])
    if len(words) > max_words:
        snippet += "…"
    return snippet


def format_collecting_reply(
    *,
    user_message: str,
    question: str,
    syndrome_label_uz: str,
    turn_count: int,
    is_first_question: bool,
) -> str:
    """Warm, natural Uzbek — one clinical question only."""
    parts: list[str] = []
    if is_first_question and syndrome_label_uz:
        parts.append(
            f"Sizda {syndrome_label_uz} yo'nalishida belgilar bor — shu bo'yicha bir necha muhim savol beraman."
        )
    elif turn_count > 0:
        echo = _short_echo(user_message)
        if echo:
            parts.append(f"{_pick_acknowledgment(turn_count)} ({echo})")
        else:
            parts.append(_pick_acknowledgment(turn_count))

    q = question.strip()
    if q and not q.endswith("?"):
        q = q + "?"
    parts.append(q)
    return " ".join(parts)


def format_recognition_reply(
    *,
    syndrome_label_uz: str,
    first_question: str,
) -> str:
    return (
        f"Sizning asosiy muammoingiz {syndrome_label_uz} bilan bog'liq ko'rinadi. "
        f"Bir necha qisqa savol beraman — aniq yordam berish uchun. {first_question.strip()}"
        + ("" if first_question.strip().endswith("?") else "?")
    )


def format_closure_reply(closure_text: str) -> str:
    return closure_text.strip()
