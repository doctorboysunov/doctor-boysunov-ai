from telegram import Update

from app.repositories.conversation_repository import upsert_user


def register_telegram_user(update: Update) -> int:
    user = update.effective_user
    return upsert_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
