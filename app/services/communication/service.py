"""Unified communication service for all outbound patient messaging."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.repositories.communication_repository import (
    create_delivery_record,
    get_delivery_record,
    list_delivery_history,
    mark_delivery_replied,
    update_delivery_status,
)
from app.services.communication.channels import get_channel_attempt_order
from app.services.communication.providers.base import ProviderContext
from app.services.communication.providers.registry import get_provider, install_default_providers

logger = logging.getLogger("doctor_boysunov.communication")


@dataclass(frozen=True)
class SendPatientMessageResult:
    success: bool
    patient_id: int
    channel: str | None
    delivery_id: int | None
    status: str | None
    attempted_channels: tuple[str, ...]
    error_message: str | None = None


def _status_from_provider(*, success: bool, delivered: bool) -> str:
    if not success:
        return "failed"
    if delivered:
        return "delivered"
    return "sent"


async def send_patient_message(
    *,
    patient_id: int,
    text: str,
    source_type: str,
    source_id: str | None = None,
    bot=None,
) -> SendPatientMessageResult:
    """Send a message using channel priority with automatic fallback."""
    install_default_providers(bot=bot)

    attempt_plan = get_channel_attempt_order(patient_id)
    if not attempt_plan:
        delivery = create_delivery_record(
            patient_id=patient_id,
            channel="telegram",
            source_type=source_type,
            source_id=source_id,
            message_text=text,
            status="failed",
            provider_name=None,
            error_message="No communication channels available for patient",
        )
        return SendPatientMessageResult(
            success=False,
            patient_id=patient_id,
            channel=None,
            delivery_id=delivery["id"],
            status="failed",
            attempted_channels=(),
            error_message="No communication channels available for patient",
        )

    attempted: list[str] = []
    parent_delivery_id: int | None = None
    last_error: str | None = None

    for attempt_number, (channel, address) in enumerate(attempt_plan, start=1):
        attempted.append(channel)
        provider = get_provider(channel)
        if provider is None or not provider.is_available():
            delivery = create_delivery_record(
                patient_id=patient_id,
                channel=channel,
                source_type=source_type,
                source_id=source_id,
                message_text=text,
                status="failed",
                provider_name=provider.provider_name if provider else None,
                error_message=f"Provider unavailable for {channel}",
                attempt_number=attempt_number,
                parent_delivery_id=parent_delivery_id,
            )
            parent_delivery_id = delivery["id"]
            last_error = delivery["error_message"]
            continue

        context = ProviderContext(
            patient_id=patient_id,
            source_type=source_type,
            source_id=source_id,
        )
        result = await provider.send(address=address, text=text, context=context)
        status = _status_from_provider(success=result.success, delivered=result.delivered)
        delivery = create_delivery_record(
            patient_id=patient_id,
            channel=channel,
            source_type=source_type,
            source_id=source_id,
            message_text=text,
            status=status,
            provider_name=result.provider_name,
            provider_message_id=result.provider_message_id,
            error_message=result.error_message,
            attempt_number=attempt_number,
            parent_delivery_id=parent_delivery_id,
        )
        parent_delivery_id = delivery["id"]

        if result.success:
            logger.info(
                "communication_sent patient_id=%s channel=%s delivery_id=%s source=%s",
                patient_id,
                channel,
                delivery["id"],
                source_type,
            )
            return SendPatientMessageResult(
                success=True,
                patient_id=patient_id,
                channel=channel,
                delivery_id=delivery["id"],
                status=status,
                attempted_channels=tuple(attempted),
            )

        last_error = result.error_message

    return SendPatientMessageResult(
        success=False,
        patient_id=patient_id,
        channel=None,
        delivery_id=parent_delivery_id,
        status="failed",
        attempted_channels=tuple(attempted),
        error_message=last_error,
    )


async def resend_delivery(*, delivery_id: int, bot=None) -> SendPatientMessageResult:
    original = get_delivery_record(delivery_id)
    return await send_patient_message(
        patient_id=original["patient_id"],
        text=original["message_text"],
        source_type="manual",
        source_id=str(original["id"]),
        bot=bot,
    )


def record_patient_reply(*, delivery_id: int, reply_text: str) -> dict:
    return mark_delivery_replied(delivery_id, reply_text=reply_text)


def mark_delivery_as_delivered(delivery_id: int, *, provider_message_id: str | None = None) -> dict:
    return update_delivery_status(
        delivery_id,
        status="delivered",
        provider_message_id=provider_message_id,
    )


def get_patient_communication_history(
    patient_id: int,
    *,
    source_type: str | None = None,
    source_id: str | None = None,
) -> list[dict]:
    return list_delivery_history(
        patient_id,
        source_type=source_type,
        source_id=source_id,
    )
