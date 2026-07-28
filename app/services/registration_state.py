"""In-memory patient location registration state (Telegram context.user_data)."""

from __future__ import annotations

from typing import Any, Literal

from telegram.ext import ContextTypes

RegistrationState = Literal["active", "paused"]
RegistrationStep = Literal[
    "full_name", "phone_number", "country", "region", "district", "address", "share_location"
]

_VALID_STEPS: tuple[str, ...] = (
    "full_name",
    "phone_number",
    "country",
    "region",
    "district",
    "address",
    "share_location",
)

REGISTRATION_STATE_KEY = "registration_state"
PENDING_REGISTRATION_STEP_KEY = "pending_registration_step"
REGISTRATION_UPDATING_KEY = "registration_updating"

# Legacy key kept for tests and backward compatibility during migration.
LOCATION_STATE_KEY = "location_registration"


def _user_data(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    if context is None or context.user_data is None:
        return None
    return context.user_data


def get_registration_state(context: ContextTypes.DEFAULT_TYPE) -> RegistrationState | None:
    data = _user_data(context)
    if data is None:
        return None
    value = data.get(REGISTRATION_STATE_KEY)
    if value in ("active", "paused"):
        return value
    return None


def get_pending_registration_step(context: ContextTypes.DEFAULT_TYPE) -> RegistrationStep | None:
    data = _user_data(context)
    if data is None:
        return None
    step = data.get(PENDING_REGISTRATION_STEP_KEY)
    if step in _VALID_STEPS:
        return step
    legacy = data.get(LOCATION_STATE_KEY)
    if isinstance(legacy, dict):
        legacy_step = legacy.get("step")
        if legacy_step in _VALID_STEPS:
            return legacy_step
    return None


def is_registration_updating(context: ContextTypes.DEFAULT_TYPE) -> bool:
    data = _user_data(context)
    if data is None:
        return False
    if REGISTRATION_UPDATING_KEY in data:
        return bool(data[REGISTRATION_UPDATING_KEY])
    legacy = data.get(LOCATION_STATE_KEY)
    if isinstance(legacy, dict):
        return bool(legacy.get("updating"))
    return False


def _sync_legacy_location_key(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = _user_data(context)
    if data is None:
        return
    state = get_registration_state(context)
    step = get_pending_registration_step(context)
    if state is None or step is None:
        data.pop(LOCATION_STATE_KEY, None)
        return
    data[LOCATION_STATE_KEY] = {
        "step": step,
        "updating": is_registration_updating(context),
    }


def start_registration(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    updating: bool = False,
    first_step: RegistrationStep | None = None,
) -> RegistrationStep:
    """Begin (or restart) the registration state machine.

    ``first_step`` lets callers resume at the first still-missing required
    field (e.g. a legacy patient who already has a location on file but no
    phone number should start at "phone_number", not "full_name" again).
    Defaults to "full_name" for a brand new registration, or "country" for
    an explicit address-update trigger (name/phone are assumed already on
    file in that case).
    """
    step: RegistrationStep = first_step or ("country" if updating else "full_name")
    data = _user_data(context)
    if data is None:
        return step
    data[REGISTRATION_STATE_KEY] = "active"
    data[PENDING_REGISTRATION_STEP_KEY] = step
    data[REGISTRATION_UPDATING_KEY] = updating
    _sync_legacy_location_key(context)
    return step


def set_registration_step(context: ContextTypes.DEFAULT_TYPE, step: RegistrationStep) -> None:
    data = _user_data(context)
    if data is None:
        return
    data[REGISTRATION_STATE_KEY] = "active"
    data[PENDING_REGISTRATION_STEP_KEY] = step
    _sync_legacy_location_key(context)


def pause_registration(context: ContextTypes.DEFAULT_TYPE) -> RegistrationStep | None:
    """Pause active registration so Medical AI can answer; keep pending step."""
    data = _user_data(context)
    if data is None:
        return None
    step = get_pending_registration_step(context)
    if step is None:
        return None
    data[REGISTRATION_STATE_KEY] = "paused"
    _sync_legacy_location_key(context)
    return step


def resume_registration(context: ContextTypes.DEFAULT_TYPE) -> RegistrationStep | None:
    data = _user_data(context)
    if data is None:
        return None
    step = get_pending_registration_step(context)
    if step is None:
        return None
    data[REGISTRATION_STATE_KEY] = "active"
    _sync_legacy_location_key(context)
    return step


def clear_registration_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = _user_data(context)
    if data is None:
        return
    data.pop(REGISTRATION_STATE_KEY, None)
    data.pop(PENDING_REGISTRATION_STEP_KEY, None)
    data.pop(REGISTRATION_UPDATING_KEY, None)
    data.pop(LOCATION_STATE_KEY, None)


def registration_snapshot(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    return {
        "registration_state": get_registration_state(context),
        "pending_registration_step": get_pending_registration_step(context),
        "registration_updating": is_registration_updating(context),
    }
