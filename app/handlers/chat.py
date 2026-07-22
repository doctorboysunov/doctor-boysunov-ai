from telegram import Update
from telegram.ext import ContextTypes

from app.services.openai_service import ask_ai


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    answer = ask_ai(user_message)
    await update.message.reply_text(answer)