"""Shared helpers for verification scripts."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from unittest.mock import AsyncMock, patch

from app.domain.conversation_flow import FlowDecision
from app.handlers.location import LocationHandleResult
from app.repositories.patient_profile_repository import (
    get_or_create_patient_profile,
    update_patient_profile,
)


def seed_default_location(user_id: int) -> None:
    """Seed a fully-registered test patient (mandatory registration fields
    included) so tests can bypass the registration gate and reach the
    consultation / booking engines directly.

    Only fills in ``full_name``/``phone_number`` if they are not already set,
    so tests that call this repeatedly (e.g. once per turn) and separately
    set a custom name via profile extraction don't get it clobbered back to
    the default on the next call.
    """
    existing = get_or_create_patient_profile(user_id)
    updates: dict = {
        "country": "O'zbekiston",
        "region": "Toshkent",
        "district": "Yunusobod",
        "city_region": "Toshkent",
        "latitude": 41.3111,
        "longitude": 69.2797,
    }
    if not existing.get("full_name"):
        updates["full_name"] = "Test Patient"
    if not existing.get("phone_number"):
        updates["phone_number"] = f"+99890{user_id % 10_000_000:07d}"
    update_patient_profile(user_id, **updates)


CONSULTATION_FLOW = FlowDecision(
    flow="patient_consultation",
    reason="test_support",
    is_admin=False,
    admin_reason="patient",
    patient_intake_detected=False,
    patient_creation_triggered=False,
    clinical_form_detected=False,
)


@contextmanager
def patient_flow_patches(*, include_start: bool = True):
    """Bypass location/registration gates so chat tests reach Medical AI."""
    with ExitStack() as stack:
        if include_start:
            stack.enter_context(
                patch("app.handlers.start.is_registration_complete", return_value=True)
            )
        stack.enter_context(patch("app.handlers.chat.is_registration_complete", return_value=True))
        stack.enter_context(
            patch(
                "app.handlers.chat.resolve_incoming_message_flow",
                return_value=CONSULTATION_FLOW,
            )
        )
        stack.enter_context(
            patch(
                "app.handlers.chat.handle_location_registration_text",
                new=AsyncMock(return_value=LocationHandleResult.NOT_IN_REGISTRATION),
            )
        )
        stack.enter_context(
            patch(
                "app.handlers.chat.handle_appointment_flow",
                new=AsyncMock(return_value=False),
            )
        )
        stack.enter_context(
            patch("app.handlers.chat.should_use_consultation_engine", return_value=False)
        )
        yield
