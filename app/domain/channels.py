"""Supported inbound/outbound patient communication channels."""

from __future__ import annotations

from typing import Literal

ChannelType = Literal[
    "telegram",
    "instagram",
    "whatsapp",
    "facebook",
    "web",
    "mobile",
]

SUPPORTED_CHANNELS: tuple[ChannelType, ...] = (
    "telegram",
    "instagram",
    "whatsapp",
    "facebook",
    "web",
    "mobile",
)

DEFAULT_CHANNEL: ChannelType = "telegram"


def is_supported_channel(channel: str) -> bool:
    return channel in SUPPORTED_CHANNELS
