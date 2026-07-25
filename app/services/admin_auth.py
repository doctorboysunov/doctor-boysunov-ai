"""Admin access control."""

from __future__ import annotations

import logging

from app.config import ADMIN_TELEGRAM_IDS
from app.repositories.admin_repository import list_admin_telegram_ids

logger = logging.getLogger("doctor_boysunov.admin_auth")


def get_all_admin_telegram_ids() -> tuple[int, ...]:
    db_ids = list_admin_telegram_ids()
    combined = set(ADMIN_TELEGRAM_IDS) | set(db_ids)
    if not combined and ADMIN_TELEGRAM_IDS:
        from app.repositories.admin_repository import seed_admin_ids_from_env

        seed_admin_ids_from_env(ADMIN_TELEGRAM_IDS)
        db_ids = list_admin_telegram_ids()
        combined = set(ADMIN_TELEGRAM_IDS) | set(db_ids)
    return tuple(sorted(combined))


def explain_admin_check(telegram_id: int) -> tuple[bool, str]:
    """Return (is_admin, human-readable reason) for diagnostics."""
    env_ids = ADMIN_TELEGRAM_IDS
    db_ids = list_admin_telegram_ids()
    all_ids = get_all_admin_telegram_ids()

    if telegram_id in env_ids and telegram_id in db_ids:
        return True, f"listed in ADMIN_TELEGRAM_IDS and admin_telegram_ids DB"
    if telegram_id in env_ids:
        return True, f"listed in ADMIN_TELEGRAM_IDS env ({list(env_ids)})"
    if telegram_id in db_ids:
        return True, f"listed in admin_telegram_ids DB ({list(db_ids)})"
    if not all_ids:
        return False, "admin list is empty — set ADMIN_TELEGRAM_IDS or run /claim_admin"
    return False, f"not in admin list (env={list(env_ids)} db={list(db_ids)})"


def is_admin(telegram_id: int) -> bool:
    result, reason = explain_admin_check(telegram_id)
    logger.info(
        "is_admin telegram_id=%s result=%s reason=%s configured_ids=%s",
        telegram_id,
        result,
        reason,
        list(get_all_admin_telegram_ids()),
    )
    return result

def admin_label(telegram_id: int, username: str | None = None) -> str:
    if username:
        return f"admin:{telegram_id} (@{username})"
    return f"admin:{telegram_id}"
