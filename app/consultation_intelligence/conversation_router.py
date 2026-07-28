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

from enum import Enum


class ConversationIntent(str, Enum):
    EMERGENCY = "emergency"
    BOOKING = "booking"
    NEW_COMPLAINT = "new_complaint"
    CONTINUE_CONSULTATION = "continue_consultation"
    GENERAL_QUESTION = "general_question"


# Short, high-confidence booking phrases — safe to match even inside a longer
# sentence because they are unambiguous requests for an appointment/call.
_BOOKING_STRONG_PATTERNS: tuple[str, ...] = (
    "i want an appointment",
    "i want an online consultation",
    "i want a consultation",
    "book me",
    "book an appointment",
    "book a consultation",
    "schedule an appointment",
    "schedule a consultation",
    "call me",
    "please call me",
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
    "onlayn korik",
    "video konsultatsiya",
    "menga qo'ng'iroq qiling",
    "qo'ng'iroq qiling",
    "qongiroq qiling",
    "telefon qiling",
    "aloqaga chiqing",
    "shifokorga yozil",
    "shifokorga yoziling",
    "klinikaga yozil",
    "klinikada qabul",
)

# Bare, standalone words that only count as booking intent when the whole
# message is short (so we don't hijack a clinical narrative that happens to
# mention "consultation"/"appointment" in passing, e.g. describing why they
# came to the doctor). Deliberately English-only here: the Uzbek equivalents
# ("qabul", "konsultatsiya", "navbat") are heavily overloaded — they also show
# up in unrelated pricing/general questions ("Qabul narxi qancha?" = "How much
# does an appointment cost?") — so those only count as booking intent as part
# of a longer, unambiguous phrase in ``_BOOKING_STRONG_PATTERNS`` above.
_BOOKING_BARE_WORDS: tuple[str, ...] = (
    "appointment",
    "consultation",
    "booking",
)

_MAX_WORDS_FOR_BARE_MATCH = 5

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
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(p in lowered for p in _BOOKING_STRONG_PATTERNS):
        return True
    word_count = len(lowered.split())
    if word_count <= _MAX_WORDS_FOR_BARE_MATCH and any(w in lowered for w in _BOOKING_BARE_WORDS):
        return True
    return False


def is_new_complaint_intent(text: str) -> bool:
    """True when the patient explicitly signals they want to switch topics."""
    lowered = (text or "").strip().lower()
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
