from telegram import Update
from telegram.ext import ContextTypes

from app.handlers.common import register_telegram_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_telegram_user(update)

    await update.message.reply_text(
        "Assalomu alaykum! Men Doctor Boysunov AI yordamchisiman."
    )
