"""Resolve patients across Telegram, Instagram, WhatsApp, Facebook, web, and mobile."""

from __future__ import annotations

from app.container import get_container
from app.domain.channels import ChannelType, DEFAULT_CHANNEL
from app.repositories import user_identity_repository as identity_repo
from app.repositories.conversation_repository import upsert_user
from app.repositories.patient_profile_repository import get_or_create_patient_profile


def resolve_channel_user(
    channel: ChannelType,
    external_id: str,
    *,
    display_name: str | None = None,
    username: str | None = None,
) -> int:
    """Return canonical user_id for any supported inbound channel."""
    existing = identity_repo.resolve_user_id(channel, external_id)
    if existing is not None:
        identity_repo.upsert_channel_identity(
            channel,
            external_id,
            user_id=existing,
            display_name=display_name,
        )
        get_or_create_patient_profile(existing)
        return existing

    if channel == DEFAULT_CHANNEL:
        user_id = upsert_user(
            telegram_id=int(external_id),
            username=username,
            full_name=display_name,
        )
        identity_repo.upsert_channel_identity(
            channel,
            external_id,
            user_id=user_id,
            display_name=display_name,
        )
    else:
        user_id = identity_repo.upsert_channel_identity(
            channel,
            external_id,
            display_name=display_name,
        )

    get_or_create_patient_profile(user_id)
    _ = get_container()  # ensure DI warms on first multi-channel resolve
    return user_id


def resolve_telegram_user(
    *,
    telegram_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> int:
    return resolve_channel_user(
        DEFAULT_CHANNEL,
        str(telegram_id),
        display_name=full_name,
        username=username,
    )
