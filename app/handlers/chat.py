import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.config import DATABASE_PATH
from app.handlers.common import register_telegram_user
from app.repositories.conversation_repository import (
    get_last_messages,
    get_or_create_active_conversation,
    save_message,
)
from app.services.openai_service import ask_ai

HISTORY_LIMIT = 10
logger = logging.getLogger("doctor_boysunov.chat")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    telegram_id = update.effective_user.id

    user_id = register_telegram_user(update)
    conversation_id = get_or_create_active_conversation(user_id)

    save_message(conversation_id, "user", user_message)

    history = get_last_messages(conversation_id, limit=HISTORY_LIMIT)

    # Proof log: full history immediately before OpenAI call.
    print("=== BEFORE ask_ai() ===")
    print(f"database={DATABASE_PATH}")
    print(f"conversation_id={conversation_id}")
    print(f"history_count={len(history)}")
    print(f"history={json.dumps(history, ensure_ascii=False, indent=2)}")

    answer = ask_ai(history)

    save_message(conversation_id, "assistant", answer)
    await update.message.reply_text(answer)
