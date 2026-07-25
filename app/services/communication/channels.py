"""Resolve patient communication channels from profile data."""

from __future__ import annotations

from app.domain.communication import (
    CHANNEL_PRIORITY_WITHOUT_TELEGRAM,
    TELEGRAM_FAILURE_FALLBACK,
)
from app.repositories.communication_repository import list_patient_channels, upsert_patient_channel
from app.repositories.conversation_repository import get_telegram_id_for_user
from app.repositories.patient_profile_repository import get_patient_profile


def sync_patient_channels(patient_id: int) -> list[dict]:
    """Persist available channels for a patient based on profile + user linkage."""
    profile = get_patient_profile(patient_id)
    channels: list[dict] = []

    telegram_id = get_telegram_id_for_user(patient_id)
    if telegram_id is not None and telegram_id > 0:
        channels.append(
            upsert_patient_channel(
                patient_id=patient_id,
                channel="telegram",
                address=str(telegram_id),
            )
        )

    if profile:
        phone = profile.get("phone_number")
        if phone:
            channels.append(
                upsert_patient_channel(
                    patient_id=patient_id,
                    channel="sms",
                    address=str(phone),
                )
            )

        push_token = profile.get("mobile_push_token")
        if push_token:
            channels.append(
                upsert_patient_channel(
                    patient_id=patient_id,
                    channel="mobile_push",
                    address=str(push_token),
                )
            )

        email = profile.get("email")
        if email:
            channels.append(
                upsert_patient_channel(
                    patient_id=patient_id,
                    channel="email",
                    address=str(email),
                )
            )

    return channels


def build_attempt_order(available_channels: set[str]) -> list[str]:
    if "telegram" in available_channels:
        order = ["telegram"]
        for channel in TELEGRAM_FAILURE_FALLBACK:
            if channel in available_channels:
                order.append(channel)
        return order
    return [channel for channel in CHANNEL_PRIORITY_WITHOUT_TELEGRAM if channel in available_channels]


def get_channel_attempt_order(patient_id: int) -> list[tuple[str, str]]:
    """Return ordered (channel, address) pairs ready for delivery attempts."""
    sync_patient_channels(patient_id)
    stored = list_patient_channels(patient_id, enabled_only=True)
    available = {item["channel"] for item in stored}
    order = build_attempt_order(available)

    address_by_channel = {item["channel"]: item["address"] for item in stored}
    return [(channel, address_by_channel[channel]) for channel in order if channel in address_by_channel]
