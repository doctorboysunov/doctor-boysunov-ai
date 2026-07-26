"""Pricing information requests."""

from __future__ import annotations

from telegram import Update

PRICING_REPLY = (
    "Konsultatsiya narxlari xizmat turiga qarab belgilanadi.\n\n"
    "Aniq narx va qabul vaqtini bilish uchun \"Navbat olmoqchiman\" deb yozing "
    "yoki klinika telefoniga qo'ng'iroq qiling."
)


async def handle_pricing_request(update: Update) -> None:
    if update.message is not None:
        await update.message.reply_text(PRICING_REPLY)
