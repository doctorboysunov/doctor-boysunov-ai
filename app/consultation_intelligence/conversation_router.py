"""Conversation router — a single prioritized intent classifier.

Every incoming patient message competes across five intents, evaluated in a
strict priority order so a message is never left in the wrong workflow:

    1. Emergency              — confirmed acute red flags always win.
    2. Booking                — patient explicitly wants an appointment/call.
    3. New complaint          — patient explicitly signals a topic switch.
    4. Continue consultation  — default while a pathway is locked in.
    5. General medical question — everything else.

This module intentionally does not re-implement emergency detection (that
already lives in ``app.safety.red_flags`` / ``app.services.consultation_red_flags``
and is deliberately conservative). It only exposes the *ordering* so callers
compose it consistently, plus the previously-missing booking/new-complaint
phrase detectors.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum


class ConversationIntent(str, Enum):
    EMERGENCY = "emergency"
    BOOKING = "booking"
    NEW_COMPLAINT = "new_complaint"
    CONTINUE_CONSULTATION = "continue_consultation"
    GENERAL_QUESTION = "general_question"


def _normalize(text: str) -> str:
    """Lowercase + fold Unicode apostrophe/quote variants to a single ASCII
    ``'`` so Uzbek phrases match regardless of which apostrophe glyph a
    patient's keyboard produces (curly quotes, modifier letters, etc.)."""
    lowered = unicodedata.normalize("NFKC", (text or "")).strip().lower()
    return re.sub(r"[\u2018\u2019\u02bb\u02bc\u2032`\u02c8]", "'", lowered)


# Explicit, unambiguous booking phrases — matched as substrings so they fire
# regardless of surrounding punctuation, politeness words ("please"), or
# where in the sentence they appear. Every literal example the product owner
# has reported ("Online consultation", "I want an appointment", "I need
# consultation", "Book me", "Clinic appointment", ...) is listed verbatim
# here (not only via the bare-word fallback below) so booking intent never
# depends on a fragile word-count heuristic.
_BOOKING_STRONG_PATTERNS: tuple[str, ...] = (
    # English
    "online consultation",
    "online appointment",
    "i want an appointment",
    "i want a appointment",
    "i want an online consultation",
    "i want a consultation",
    "i want consultation",
    "i need consultation",
    "i need a consultation",
    "i need an appointment",
    "i need appointment",
    "book me",
    "book an appointment",
    "book a consultation",
    "book appointment",
    "clinic appointment",
    "schedule an appointment",
    "schedule a consultation",
    "call me",
    "please call me",
    "can you call me",
    "set up an appointment",
    "set up a consultation",
    "arrange an appointment",
    "arrange a consultation",
    "make an appointment",
    "make a booking",
    # Uzbek
    "navbat olmoqchiman",
    "navbatga yozil",
    "qabulga yoziling",
    "qabulga yozil",
    "meni band qiling",
    "band qiling",
    "band qilib",
    "onlayn konsultatsiya",
    "onlayn qabul",
    "onlayn ko'rik",
    "video konsultatsiya",
    "menga qo'ng'iroq qiling",
    "qo'ng'iroq qiling",
    "telefon qiling",
    "aloqaga chiqing",
    "shifokorga yozil",
    "shifokorga yoziling",
    "klinikaga yozil",
    "klinikaga borsam",
    "klinikada qabul",
    "klinikaga yozilmoqchiman",
)

# Bare, standalone words that only count as booking intent when the whole
# message is short AND has no pricing/cost wording (so we don't hijack a
# clinical narrative or a pricing question that happens to mention
# "consultation"/"appointment" in passing, e.g. "How much is a
# consultation?" or "Qabul narxi qancha?").
_BOOKING_BARE_WORDS: tuple[str, ...] = (
    "appointment",
    "consultation",
    "booking",
)

_MAX_WORDS_FOR_BARE_MATCH = 6

_PRICING_GUARD_WORDS: tuple[str, ...] = (
    "narx",
    "narxi",
    "qancha",
    "qiymat",
    "summa",
    "price",
    "cost",
    "how much",
    "fee",
)

_NEW_COMPLAINT_PATTERNS: tuple[str, ...] = (
    "yangi muammo",
    "boshqa shikoyat",
    "boshqa muammo",
    "restart",
    "boshqadan",
    "new complaint",
    "another problem",
    "different problem",
)


def is_booking_intent(text: str) -> bool:
    """True when the patient is asking to book/schedule/be called, not describing symptoms."""
    lowered = _normalize(text)
    if not lowered:
        return False
    if any(p in lowered for p in _BOOKING_STRONG_PATTERNS):
        return True
    if any(g in lowered for g in _PRICING_GUARD_WORDS):
        return False
    word_count = len(lowered.split())
    if word_count <= _MAX_WORDS_FOR_BARE_MATCH and any(w in lowered for w in _BOOKING_BARE_WORDS):
        return True
    return False


def is_new_complaint_intent(text: str) -> bool:
    """True when the patient explicitly signals they want to switch topics."""
    lowered = _normalize(text)
    if not lowered:
        return False
    return any(p in lowered for p in _NEW_COMPLAINT_PATTERNS)


def classify_conversation_intent(
    text: str,
    *,
    is_confirmed_emergency: bool = False,
    pathway_locked: bool = False,
) -> ConversationIntent:
    """Classify a single incoming message against the five priority intents.

    ``is_confirmed_emergency`` must be computed by the caller using the
    existing (deliberately conservative) red-flag detectors — this router
    does not duplicate that logic, it only honors its priority.

    Booking is checked before "continue consultation" unconditionally — a
    patient asking to book/be called must never be kept inside the
    diagnostic questioning flow, active session or not.
    """
    if is_confirmed_emergency:
        return ConversationIntent.EMERGENCY
    if is_booking_intent(text):
        return ConversationIntent.BOOKING
    if is_new_complaint_intent(text):
        return ConversationIntent.NEW_COMPLAINT
    if pathway_locked:
        return ConversationIntent.CONTINUE_CONSULTATION
    return ConversationIntent.GENERAL_QUESTION
