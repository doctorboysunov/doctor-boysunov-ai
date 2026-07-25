"""Doctor dashboard quick actions."""

from __future__ import annotations

from app.repositories.appointment_repository import create_appointment
from app.repositories.follow_up_repository import mark_follow_up_completed, reschedule_follow_up
from app.repositories.patient_intake_repository import get_patient_card
from app.services.communication import send_patient_message

QUICK_ACTIONS = (
    "open_card",
    "send_telegram",
    "send_sms",
    "mark_completed",
    "reschedule_follow_up",
    "book_appointment",
)


async def action_open_patient_card(patient_id: int) -> dict:
    card = get_patient_card(patient_id)
    if card is None:
        raise ValueError(f"Patient not found: {patient_id}")
    card["actions"] = list(QUICK_ACTIONS)
    return card


async def action_send_telegram(
    *,
    patient_id: int,
    text: str,
    bot,
    source_id: str | None = None,
) -> dict:
    result = await send_patient_message(
        patient_id=patient_id,
        text=text,
        source_type="reminder",
        source_id=source_id,
        bot=bot,
    )
    return {
        "success": result.success,
        "channel": result.channel,
        "delivery_id": result.delivery_id,
        "status": result.status,
    }


async def action_send_sms(
    *,
    patient_id: int,
    text: str,
    bot=None,
    source_id: str | None = None,
) -> dict:
    from app.services.communication.providers.registry import get_provider, install_default_providers

    install_default_providers(bot=bot)
    provider = get_provider("sms")
    if provider is None or not provider.is_available():
        return {"success": False, "error": "SMS provider unavailable"}

    from app.services.communication.channels import sync_patient_channels
    from app.repositories.communication_repository import list_patient_channels, create_delivery_record
    from app.services.communication.providers.base import ProviderContext

    sync_patient_channels(patient_id)
    channels = [item for item in list_patient_channels(patient_id) if item["channel"] == "sms"]
    if not channels:
        return {"success": False, "error": "Patient has no SMS channel"}

    context = ProviderContext(patient_id=patient_id, source_type="reminder", source_id=source_id)
    send_result = await provider.send(address=channels[0]["address"], text=text, context=context)
    status = "delivered" if send_result.delivered else ("sent" if send_result.success else "failed")
    delivery = create_delivery_record(
        patient_id=patient_id,
        channel="sms",
        source_type="reminder",
        source_id=source_id,
        message_text=text,
        status=status,
        provider_name=send_result.provider_name,
        provider_message_id=send_result.provider_message_id,
        error_message=send_result.error_message,
    )
    return {
        "success": send_result.success,
        "channel": "sms",
        "delivery_id": delivery["id"],
        "status": status,
    }


async def action_mark_follow_up_completed(follow_up_id: int) -> dict:
    follow_up = mark_follow_up_completed(follow_up_id)
    return {"success": True, "follow_up": follow_up}


async def action_reschedule_follow_up(follow_up_id: int, *, scheduled_date: str) -> dict:
    follow_up = reschedule_follow_up(follow_up_id, scheduled_date=scheduled_date)
    return {"success": True, "follow_up": follow_up}


async def action_book_appointment(
    *,
    patient_id: int,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    complaint: str,
) -> dict:
    appointment = create_appointment(
        patient_id=patient_id,
        doctor_name=doctor_name,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        complaint=complaint,
    )
    return {"success": True, "appointment": appointment}
