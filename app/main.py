import asyncio
import logging
import os

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import BOT_TOKEN, DATABASE_PATH, OPENAI_MODEL, DASHBOARD_MORNING_HOUR
from app.db.connection import get_connection, init_db
from app.handlers.admin_appointments import (
    admin_appointments,
    admin_cancel_appt,
    admin_cancelled,
    admin_confirm,
    admin_confirmed,
    admin_note,
    admin_pending,
    admin_reschedule,
    admin_today,
    admin_tomorrow,
)
from app.handlers.admin_dashboard import (
    admin_dashboard,
    admin_dashboard_generate,
    admin_dashboard_send,
)
from app.handlers.admin_communications import admin_comm_history, admin_resend_comm
from app.handlers.admin_follow_ups import (
    admin_followups,
    admin_followups_due,
    admin_run_followups,
    admin_start_treatment,
)
from app.handlers.start import claim_admin, myid, start
from app.handlers.chat import chat
from app.handlers.documents import handle_patient_file
from app.handlers.location import handle_location_share
from app.handlers.patient_intake import (
    handle_patient_contact,
    handle_patient_voice,
    try_capture_from_photo,
)
from app.logging_setup import LOG_FILE, setup_logging
from app.services.admin_bootstrap import bootstrap_admin_registry
from app.services.dashboard_service import send_morning_dashboard_to_admins
from app.services.follow_up_processor import process_due_follow_ups
from app.services.routing_trace import ROUTING_FIX_VERSION


async def _process_due_follow_ups_job(context) -> None:
    await process_due_follow_ups(context.bot)


async def _morning_dashboard_job(context) -> None:
    await send_morning_dashboard_to_admins(context.bot)


async def handle_photo_message(update, context) -> None:
    if await try_capture_from_photo(update, context):
        return
    await handle_patient_file(update, context)


async def _log_handler_error(update: object, context) -> None:
    err_logger = logging.getLogger("doctor_boysunov.telegram")
    err_logger.exception("telegram_handler_error update=%r", update, exc_info=context.error)
    message = getattr(update, "effective_message", None) if update else None
    if message is not None:
        await message.reply_text(
            "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki matn ko'rinishida yuboring."
        )


def main():
    logger = setup_logging()
    init_db()
    admins = bootstrap_admin_registry()

    with get_connection() as conn:
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    logger.info("=== BOT STARTUP ===")
    logger.info("memory_enabled=True")
    logger.info("database_path=%s", DATABASE_PATH)
    logger.info("openai_model=%s", OPENAI_MODEL)
    logger.info("debug_log=%s", LOG_FILE)
    logger.info("admin_telegram_ids=%s", list(admins))
    logger.info("doctor_admin_mode=%s", "enabled" if admins else "DISABLED")
    logger.info("entrypoint=app.main with SQLite conversation memory")
    git_commit = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")
    logger.info("git_commit_sha=%s", git_commit)
    logger.info("routing_fix_version=%s", ROUTING_FIX_VERSION)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(_log_handler_error)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("claim_admin", claim_admin))
    app.add_handler(CommandHandler("today", admin_today))
    app.add_handler(CommandHandler("tomorrow", admin_tomorrow))
    app.add_handler(CommandHandler("appointments", admin_appointments))
    app.add_handler(CommandHandler("pending", admin_pending))
    app.add_handler(CommandHandler("confirmed", admin_confirmed))
    app.add_handler(CommandHandler("cancelled", admin_cancelled))
    app.add_handler(CommandHandler("confirm", admin_confirm))
    app.add_handler(CommandHandler("reschedule", admin_reschedule))
    app.add_handler(CommandHandler("cancel_appt", admin_cancel_appt))
    app.add_handler(CommandHandler("note", admin_note))
    app.add_handler(CommandHandler("start_treatment", admin_start_treatment))
    app.add_handler(CommandHandler("followups", admin_followups))
    app.add_handler(CommandHandler("followups_due", admin_followups_due))
    app.add_handler(CommandHandler("run_followups", admin_run_followups))
    app.add_handler(CommandHandler("comm_history", admin_comm_history))
    app.add_handler(CommandHandler("resend_comm", admin_resend_comm))
    app.add_handler(CommandHandler("dashboard", admin_dashboard))
    app.add_handler(CommandHandler("dashboard_generate", admin_dashboard_generate))
    app.add_handler(CommandHandler("dashboard_send", admin_dashboard_send))
    app.add_handler(MessageHandler(filters.CONTACT, handle_patient_contact))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_patient_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location_share))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_patient_file))

    if app.job_queue is not None:
        from datetime import time

        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("Asia/Tashkent")
        except Exception:  # noqa: BLE001
            tz = None

        app.job_queue.run_once(_process_due_follow_ups_job, when=10)
        app.job_queue.run_repeating(_process_due_follow_ups_job, interval=3600, first=120)
        app.job_queue.run_daily(
            _morning_dashboard_job,
            time=time(hour=DASHBOARD_MORNING_HOUR, minute=0, tzinfo=tz),
            name="morning_dashboard",
        )

    print(
        f"ClinicOS AI ishga tushdi... memory=ON commit={git_commit} "
        f"routing_fix={ROUTING_FIX_VERSION} db={DATABASE_PATH} log={LOG_FILE}"
    )
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()


if __name__ == "__main__":
    main()
