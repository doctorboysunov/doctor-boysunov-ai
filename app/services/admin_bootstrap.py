"""Admin bootstrap and diagnostics."""

from __future__ import annotations

import logging

from app.config import ADMIN_SETUP_PIN, ADMIN_TELEGRAM_IDS
from app.repositories.admin_repository import (
    add_admin_telegram_id,
    list_admin_telegram_ids,
    seed_admin_ids_from_env,
)
from app.services.admin_auth import get_all_admin_telegram_ids

logger = logging.getLogger("doctor_boysunov.admin_bootstrap")


def bootstrap_admin_registry() -> tuple[int, ...]:
    """Load admin IDs from env into SQLite and return the active admin set."""
    seed_admin_ids_from_env(ADMIN_TELEGRAM_IDS)
    admins = get_all_admin_telegram_ids()
    if not admins:
        logger.warning(
            "NO_ADMIN_TELEGRAM_IDS configured. "
            "Doctor/Admin mode is disabled until ADMIN_TELEGRAM_IDS is set "
            "or an admin runs /claim_admin <pin>."
        )
    else:
        logger.info(
            "admin_registry_ready count=%s env_ids=%s db_ids=%s merged=%s",
            len(admins),
            list(ADMIN_TELEGRAM_IDS),
            list(list_admin_telegram_ids()),
            list(admins),
        )
    return admins


def claim_admin_with_pin(telegram_id: int, pin: str) -> tuple[bool, str]:
    if not ADMIN_SETUP_PIN:
        return False, "ADMIN_SETUP_PIN is not configured on the server."
    if pin.strip() != ADMIN_SETUP_PIN.strip():
        return False, "Noto'g'ri PIN."
    add_admin_telegram_id(telegram_id, source="claim_admin")
    logger.info("admin_claimed telegram_id=%s", telegram_id)
    return True, (
        f"Administrator faollashtirildi.\n"
        f"Telegram ID: {telegram_id}\n"
        f"Normal AI assistant faol. Yangi bemor: /add_patient yoki \"Add Patient\" tugmasi."
    )
