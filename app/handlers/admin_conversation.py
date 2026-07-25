"""Doctor/admin conversation mode — uses the same routed text pipeline as chat."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.chat import process_text_message


async def handle_admin_chat_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    if message is None or not message.text:
        return False

    await process_text_message(
        update,
        context,
        message.text,
        entry_handler="admin_conversation.py::handle_admin_chat_text",
    )
    return True
