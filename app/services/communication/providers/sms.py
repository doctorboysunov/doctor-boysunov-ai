"""SMS communication provider."""

from __future__ import annotations

import logging

from app.config import SMS_ENABLED
from app.services.communication.providers.base import ProviderContext, ProviderSendResult

logger = logging.getLogger("doctor_boysunov.communication.sms")


class SmsProvider:
    channel = "sms"
    provider_name = "sms_gateway"

    def is_available(self) -> bool:
        return SMS_ENABLED

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
                error_message="SMS provider is not configured",
            )

        # Provider hook: replace with Twilio/etc. when credentials are configured.
        message_id = f"sms-{context.patient_id}-{hash(text) & 0xFFFF:x}"
        logger.info(
            "sms_sent patient_id=%s phone=%s message_id=%s",
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
