"""Communication provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderSendResult:
    success: bool
    provider_name: str
    provider_message_id: str | None = None
    delivered: bool = False
    error_message: str | None = None


@dataclass(frozen=True)
class ProviderContext:
    patient_id: int
    source_type: str
    source_id: str | None = None


class CommunicationProvider(Protocol):
    channel: str
    provider_name: str

    def is_available(self) -> bool:
        """True when provider is configured and can send."""

    async def send(
        self,
        *,
        address: str,
        text: str,
        context: ProviderContext,
    ) -> ProviderSendResult:
        ...
