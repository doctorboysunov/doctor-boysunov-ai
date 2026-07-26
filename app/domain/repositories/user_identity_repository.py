"""User identity repository interface — multi-channel patient resolution."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.channels import ChannelType


class UserIdentityRepository(Protocol):
    def resolve_user_id(self, channel: ChannelType, external_id: str) -> int | None: ...

    def upsert_channel_identity(
        self,
        channel: ChannelType,
        external_id: str,
        *,
        user_id: int | None = None,
        display_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int: ...

    def list_user_channels(self, user_id: int) -> list[dict[str, Any]]: ...
