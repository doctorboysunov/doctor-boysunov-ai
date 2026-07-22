from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN
from app.handlers.start import start
from app.handlers.chat import chat


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, chat)
    )

    print("ClinicOS AI ishga tushdi...")
    app.run_polling()


if name == "__main__":
    main()