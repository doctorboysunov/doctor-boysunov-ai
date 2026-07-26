#!/usr/bin/env python3
"""Phase 2 Step 2.9 — multi-channel identity verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_2_9.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-step-2-9-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-step-2-9-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.application.identity.resolve_user import resolve_channel_user  # noqa: E402
from app.container import bootstrap, get_container  # noqa: E402
from app.domain.channels import SUPPORTED_CHANNELS  # noqa: E402


def main() -> int:
    get_container.cache_clear()
    container = bootstrap()

    telegram_user = resolve_channel_user(
        "telegram",
        "880001",
        display_name="Telegram Patient",
        username="tg_patient",
    )
    whatsapp_user = resolve_channel_user(
        "whatsapp",
        "+998901112233",
        display_name="WhatsApp Patient",
    )
    instagram_user = resolve_channel_user(
        "instagram",
        "insta_12345",
        display_name="Instagram Patient",
    )
    assert telegram_user != whatsapp_user
    assert whatsapp_user != instagram_user

    # Link Facebook to existing Telegram patient
    facebook_user = resolve_channel_user(
        "facebook",
        "fb_998877",
        display_name="Facebook Patient",
    )
    container.identities.upsert_channel_identity(
        "facebook",
        "fb_linked",
        user_id=telegram_user,
        display_name="Linked Facebook",
    )
    linked = container.identities.resolve_user_id("facebook", "fb_linked")
    assert linked == telegram_user

    channels = container.identities.list_user_channels(telegram_user)
    channel_names = {item["channel"] for item in channels}
    assert "telegram" in channel_names
    assert "facebook" in channel_names

    tg_conv = container.conversations.get_or_create_active_conversation(
        telegram_user,
        channel="telegram",
    )
    wa_conv = container.conversations.get_or_create_active_conversation(
        whatsapp_user,
        channel="whatsapp",
    )
    assert tg_conv != wa_conv

    for channel in SUPPORTED_CHANNELS:
        assert channel in {
            "telegram",
            "instagram",
            "whatsapp",
            "facebook",
            "web",
            "mobile",
        }

    print(
        "Phase 2 Step 2.9 OK: multi-channel identities, per-channel conversations, user linking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
