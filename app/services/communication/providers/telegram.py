"""Telegram communication provider."""

from __future__ import annotations

import logging

from telegram import Bot

from app.repositories.conversation_repository import (
    get_or_create_active_conversation,
    save_message,
)
from app.services.communication.providers.base import ProviderContext, ProviderSendResult

logger = logging.getLogger("doctor_boysunov.communication.telegram")


class TelegramProvider:
    channel = "telegram"
    provider_name = "telegram_bot"

    def __init__(self, *, bot: Bot | None = None) -> None:
        self._bot = bot

    def set_bot(self, bot: Bot | None) -> None:
        self._bot = bot

    def is_available(self) -> bool:
        return self._bot is not None

    async def send(
        self,
        *,
        address: str,
        text: str,
        context: ProviderContext,
    ) -> ProviderSendResult:
        if self._bot is None:
            return ProviderSendResult(
                success=False,
                provider_name=self.provider_name,
                error_message="Telegram bot is not configured",
            )

        try:
            telegram_id = int(address)
        except ValueError:
            return ProviderSendResult(
                success=False,
                provider_name=self.provider_name,
                error_message=f"Invalid telegram address: {address!r}",
            )

        if telegram_id <= 0:
            return ProviderSendResult(
                success=False,
                provider_name=self.provider_name,
                error_message="Telegram ID is not linked",
            )

        try:
            conversation_id = get_or_create_active_conversation(context.patient_id)
            save_message(conversation_id, "assistant", text)
            message = await self._bot.send_message(chat_id=telegram_id, text=text)
            message_id = str(message.message_id) if message is not None else None
            logger.info(
                "telegram_sent patient_id=%s telegram_id=%s message_id=%s",
                context.patient_id,
                telegram_id,
                message_id,
            )
            return ProviderSendResult(
                success=True,
                provider_name=self.provider_name,
                provider_message_id=message_id,
                delivered=True,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary
            logger.warning(
                "telegram_failed patient_id=%s telegram_id=%s error=%s",
                context.patient_id,
                telegram_id,
                exc,
            )
            return ProviderSendResult(
                success=False,
                provider_name=self.provider_name,
                error_message=str(exc),
            )
