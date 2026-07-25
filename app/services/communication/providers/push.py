"""Mobile push notification provider."""

from __future__ import annotations

import logging

from app.config import PUSH_ENABLED
from app.services.communication.providers.base import ProviderContext, ProviderSendResult

logger = logging.getLogger("doctor_boysunov.communication.push")


class MobilePushProvider:
    channel = "mobile_push"
    provider_name = "mobile_push_gateway"

    def is_available(self) -> bool:
        return PUSH_ENABLED

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
                error_message="Push provider is not configured",
            )

        message_id = f"push-{context.patient_id}-{hash(text) & 0xFFFF:x}"
        logger.info(
            "push_sent patient_id=%s token=%s message_id=%s",
            context.patient_id,
            address[:12],
            message_id,
        )
        return ProviderSendResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=message_id,
            delivered=False,
        )
