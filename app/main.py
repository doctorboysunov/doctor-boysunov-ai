import os

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN, DATABASE_PATH, OPENAI_MODEL
from app.db.connection import get_connection, init_db
from app.handlers.start import start
from app.handlers.chat import chat
from app.handlers.documents import handle_patient_file
from app.logging_setup import LOG_FILE, setup_logging


def main():
    logger = setup_logging()
    init_db()

    with get_connection() as conn:
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    logger.info("=== BOT STARTUP ===")
    logger.info("memory_enabled=True")
    logger.info("database_path=%s", DATABASE_PATH)
    logger.info("openai_model=%s", OPENAI_MODEL)
    logger.info("debug_log=%s", LOG_FILE)
    logger.info("existing_messages_in_db=%s", message_count)
    logger.info("entrypoint=app.main with SQLite conversation memory")
    git_commit = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")
    logger.info("git_commit_sha=%s", git_commit)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.PHOTO, handle_patient_file))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_patient_file))

    print(
        f"ClinicOS AI ishga tushdi... memory=ON commit={git_commit} "
        f"db={DATABASE_PATH} log={LOG_FILE}"
    )
    app.run_polling()


if __name__ == "__main__":
    main()
