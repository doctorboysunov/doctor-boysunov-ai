from telegram import Update
from telegram.ext import ContextTypes

from app.domain.conversation_mode import is_doctor_admin_mode
from app.handlers.common import register_telegram_user
from app.handlers.location import start_location_registration
from app.repositories.patient_profile_repository import get_or_create_patient_profile
from app.services.admin_bootstrap import claim_admin_with_pin
from app.services.location_profile import has_location_stored


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_doctor_admin_mode(user.id):
        await update.message.reply_text(
            "Doctor/Admin mode faol.\n\n"
            "Normal AI assistant: savollaringizni bemalol yozing.\n"
            "Buyruqlar: /dashboard, /today, /myid"
        )
        return

    user_id = register_telegram_user(update)
    profile = get_or_create_patient_profile(user_id)

    if not has_location_stored(profile):
        prompt = start_location_registration(context)
        await update.message.reply_text(prompt, reply_markup=None)
        return prompt

    welcome = "Assalomu alaykum! Men Doctor Boysunov AI yordamchisiman."
    await update.message.reply_text(welcome)
    return welcome


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    admin_flag = "Ha" if is_doctor_admin_mode(user.id) else "Yo'q"
    await update.message.reply_text(
        f"Telegram ID: {user.id}\n"
        f"Doctor/Admin mode: {admin_flag}\n\n"
        "Admin bo'lish uchun serverda ADMIN_TELEGRAM_IDS ga shu ID ni qo'shing "
        "yoki /claim_admin <pin> buyrug'ini ishlating."
    )


async def claim_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Foydalanish: /claim_admin <pin>")
        return
    ok, message = claim_admin_with_pin(update.effective_user.id, context.args[0])
    await update.message.reply_text(message)
