"""Conversation mode based on user role."""

from __future__ import annotations

from typing import Literal

from app.services.admin_auth import explain_admin_check

ConversationMode = Literal["doctor_admin", "patient"]


def resolve_conversation_mode(telegram_id: int) -> ConversationMode:
    is_admin_user, reason = explain_admin_check(telegram_id)
    if is_admin_user:
        return "doctor_admin"
    return "patient"


def resolve_conversation_mode_with_reason(telegram_id: int) -> tuple[ConversationMode, bool, str]:
    is_admin_user, reason = explain_admin_check(telegram_id)
    if is_admin_user:
        return "doctor_admin", True, reason
    return "patient", False, reason


def is_doctor_admin_mode(telegram_id: int) -> bool:
    return resolve_conversation_mode(telegram_id) == "doctor_admin"
