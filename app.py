from telegram import Update

from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from openai import OpenAI

from dotenv import load_dotenv

import os

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

        "Assalomu alaykum! Men Doctor Boysunov AI yordamchisiman."

    )
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    response = client.responses.create(
        model="gpt-5.5",
        input=user_message
    )

    await update.message.reply_text(response.output_text)
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
print("Bot ishga tushdi...")

app.run_polling()