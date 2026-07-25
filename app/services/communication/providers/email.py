"""Email communication provider."""

from __future__ import annotations

import logging

from app.config import EMAIL_ENABLED
from app.services.communication.providers.base import ProviderContext, ProviderSendResult

logger = logging.getLogger("doctor_boysunov.communication.email")


class EmailProvider:
    channel = "email"
    provider_name = "email_gateway"

    def is_available(self) -> bool:
        return EMAIL_ENABLED

    async def send(
        self,
        *,
        address: str,
        text: str,
        context: ProviderContext,
    ) -> ProviderSendResult:
        if not self.is_available():
            return ProviderSendResult(
                success=False,
                provider_name=self.provider_name,
                error_message="Email provider is not configured",
            )

        message_id = f"email-{context.patient_id}-{hash(text) & 0xFFFF:x}"
        logger.info(
            "email_sent patient_id=%s email=%s message_id=%s",
            context.patient_id,
            address,
            message_id,
        )
        return ProviderSendResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=message_id,
            delivered=False,
        )
