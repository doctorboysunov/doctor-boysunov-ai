"""Shared helpers for verification scripts."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from unittest.mock import AsyncMock, patch

from app.domain.conversation_flow import FlowDecision
from app.handlers.location import LocationHandleResult
from app.repositories.patient_profile_repository import update_patient_profile


def seed_default_location(user_id: int) -> None:
    update_patient_profile(
        user_id,
        country="O'zbekiston",
        region="Toshkent",
        district="Yunusobod",
        city_region="Toshkent",
        latitude=41.3111,
        longitude=69.2797,
    )


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
                patch("app.handlers.start.has_location_stored", return_value=True)
            )
        stack.enter_context(patch("app.handlers.chat.has_location_stored", return_value=True))
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
