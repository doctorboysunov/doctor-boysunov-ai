"""Communication channel and delivery status definitions."""

from __future__ import annotations

COMMUNICATION_CHANNELS = ("telegram", "mobile_push", "sms", "email")

# Priority when Telegram is unavailable.
CHANNEL_PRIORITY_WITHOUT_TELEGRAM = ("mobile_push", "sms", "email")

# Fallback chain after Telegram fails.
TELEGRAM_FAILURE_FALLBACK = ("sms", "mobile_push", "email")

DELIVERY_STATUSES = ("sent", "delivered", "failed", "replied")

COMMUNICATION_SOURCES = (
    "follow_up",
    "appointment",
    "reminder",
    "marketing",
    "manual",
)

CHANNEL_LABELS = {
    "telegram": "Telegram",
    "mobile_push": "Mobile Push",
    "sms": "SMS",
    "email": "Email",
}
