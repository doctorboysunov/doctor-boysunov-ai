from telegram import Update

from app.repositories.conversation_repository import upsert_user
from app.repositories.patient_profile_repository import get_or_create_patient_profile


def register_telegram_user(update: Update) -> int:
    user = update.effective_user
    user_id = upsert_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
    get_or_create_patient_profile(user_id)
    return user_id
