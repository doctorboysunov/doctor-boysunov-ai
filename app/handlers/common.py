from telegram import Update

from app.application.identity.resolve_user import resolve_telegram_user


def get_telegram_user_id(update: Update) -> int | None:
    """Resolve sender Telegram user ID (effective_user or message.from_user)."""
    if update.effective_user is not None:
        return update.effective_user.id
    message = update.message
    if message is not None and message.from_user is not None:
        return message.from_user.id
    return None


def register_telegram_user(update: Update) -> int:
    user = update.effective_user or (
        update.message.from_user if update.message is not None else None
    )
    if user is None:
        raise ValueError("Telegram update has no sender user")
    return resolve_telegram_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
