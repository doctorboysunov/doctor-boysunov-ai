"""Admin conversation state — explicit registration vs normal AI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from telegram.ext import ContextTypes

from app.repositories.admin_session_repository import (
    clear_patient_registration_mode,
    complete_patient_creation_session,
    expire_stale_registration_mode,
    get_admin_session,
    is_patient_registration_mode_active,
    start_patient_registration_mode,
    upsert_admin_session,
)

ADMIN_STATE_KEY = "admin_conversation"

AdminMode = Literal["normal_ai", "doctor_visit", "patient_registration"]


@dataclass
class AdminConversationState:
    mode: AdminMode
    patient_id: int | None
    patient_name: str | None
    visit_id: int | None = None
    registration_active: bool = False


def _sync_context(context: ContextTypes.DEFAULT_TYPE, session: dict[str, Any] | None) -> None:
    user_data = getattr(context, "user_data", None)
    if user_data is None:
        return
    if session is None:
        user_data.pop(ADMIN_STATE_KEY, None)
        return
    user_data[ADMIN_STATE_KEY] = {
        "mode": session["mode"],
        "patient_id": session.get("active_patient_id"),
        "patient_name": session.get("active_patient_name"),
        "visit_id": session.get("visit_id"),
        "registration_active": session.get("mode") == "patient_registration",
    }


def get_admin_state(
    context: ContextTypes.DEFAULT_TYPE | None,
    *,
    admin_telegram_id: int | None = None,
) -> AdminConversationState | None:
    session = None
    if admin_telegram_id is not None:
        expire_stale_registration_mode(admin_telegram_id)
        session = get_admin_session(admin_telegram_id)
        if context is not None:
            _sync_context(context, session)

    if session is None:
        return None

    mode = session["mode"]
    if mode not in {"normal_ai", "doctor_visit", "patient_registration"}:
        return None

    patient_id = session.get("active_patient_id")
    patient_name = session.get("active_patient_name")
    visit_id = session.get("visit_id")
    return AdminConversationState(
        mode=mode,
        patient_id=int(patient_id) if patient_id is not None else None,
        patient_name=patient_name,
        visit_id=int(visit_id) if visit_id is not None else None,
        registration_active=mode == "patient_registration",
    )


def enter_patient_registration_mode(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
) -> AdminConversationState:
    session = start_patient_registration_mode(admin_telegram_id)
    _sync_context(context, session)
    return AdminConversationState(
        mode="patient_registration",
        patient_id=session.get("active_patient_id"),
        patient_name=session.get("active_patient_name"),
        visit_id=session.get("visit_id"),
        registration_active=True,
    )


def complete_patient_creation(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
    patient_id: int,
    patient_name: str,
    visit_id: int | None = None,
) -> AdminConversationState:
    session = complete_patient_creation_session(
        admin_telegram_id,
        patient_id=patient_id,
        patient_name=patient_name,
        visit_id=visit_id,
    )
    _sync_context(context, session)
    return AdminConversationState(
        mode="normal_ai",
        patient_id=patient_id,
        patient_name=patient_name,
        visit_id=visit_id,
        registration_active=False,
    )


def cancel_patient_registration(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
) -> None:
    session = clear_patient_registration_mode(admin_telegram_id)
    _sync_context(context, session)


def enter_normal_ai_mode(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
    patient_id: int | None = None,
    patient_name: str | None = None,
    visit_id: int | None = None,
) -> AdminConversationState:
    session = upsert_admin_session(
        admin_telegram_id,
        mode="normal_ai",
        active_patient_id=patient_id,
        active_patient_name=patient_name,
        visit_id=visit_id,
        registration_started_at=None,
    )
    _sync_context(context, session)
    return AdminConversationState(
        mode="normal_ai",
        patient_id=patient_id,
        patient_name=patient_name,
        visit_id=visit_id,
        registration_active=False,
    )


def enter_doctor_visit(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
    patient_id: int,
    patient_name: str,
    visit_id: int | None = None,
) -> AdminConversationState:
    session = upsert_admin_session(
        admin_telegram_id,
        mode="doctor_visit",
        active_patient_id=patient_id,
        active_patient_name=patient_name,
        visit_id=visit_id,
        registration_started_at=None,
    )
    _sync_context(context, session)
    return AdminConversationState(
        mode="doctor_visit",
        patient_id=patient_id,
        patient_name=patient_name,
        visit_id=visit_id,
        registration_active=False,
    )


def update_active_visit(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_telegram_id: int,
    visit_id: int,
) -> None:
    state = get_admin_state(context, admin_telegram_id=admin_telegram_id)
    if state is None or state.patient_id is None or state.patient_name is None:
        return
    enter_normal_ai_mode(
        context,
        admin_telegram_id=admin_telegram_id,
        patient_id=state.patient_id,
        patient_name=state.patient_name,
        visit_id=visit_id,
    )


def registration_mode_active(admin_telegram_id: int) -> bool:
    return is_patient_registration_mode_active(admin_telegram_id)
