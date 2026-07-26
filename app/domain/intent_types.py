"""Intent and module types for the AI message router."""

from __future__ import annotations

from typing import Literal

MessageIntent = Literal[
    "new_patient",
    "existing_patient",
    "medical_question",
    "follow_up",
    "appointment",
    "clinic_location",
    "pricing",
    "general_conversation",
    "admin_command",
]

TargetModule = Literal[
    "patient_creation",
    "doctor_visit",
    "medical_consultation",
    "follow_up_reply",
    "appointment_booking",
    "clinic_locator",
    "pricing_info",
    "general_chat",
    "patient_registration",
]

INTENT_LABELS: dict[str, str] = {
    "new_patient": "New Patient",
    "existing_patient": "Existing Patient",
    "medical_question": "Medical Question",
    "follow_up": "Follow-up",
    "appointment": "Appointment",
    "clinic_location": "Clinic Location",
    "pricing": "Pricing",
    "general_conversation": "General Conversation",
    "admin_command": "Admin Command",
}

MODULE_LABELS: dict[str, str] = {
    "patient_creation": "Patient Creation",
    "doctor_visit": "Doctor Visit",
    "medical_consultation": "Medical Consultation",
    "follow_up_reply": "Follow-up Reply",
    "appointment_booking": "Appointment Booking",
    "clinic_locator": "Clinic Locator",
    "pricing_info": "Pricing Info",
    "general_chat": "General Chat",
    "patient_registration": "Patient Registration",
}
