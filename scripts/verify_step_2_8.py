#!/usr/bin/env python3
"""Phase 2 Step 2.8 — cross-conversation recall verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_step_2_8.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-step-2-8-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-step-2-8-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.application.chat.load_conversation_context import load_conversation_context  # noqa: E402
from app.container import bootstrap, get_container  # noqa: E402
from app.repositories.conversation_repository import (  # noqa: E402
    build_conversation_summary,
    close_conversation,
    save_message,
)


def main() -> int:
    get_container.cache_clear()
    container = bootstrap()
    user_id = container.users.upsert_telegram_user(720001, full_name="Recall Test")

    conv1 = container.conversations.get_or_create_active_conversation(user_id)
    save_message(conv1, "user", "Mening ismim Dilshod.")
    save_message(conv1, "assistant", "Tanishganimdan xursandman, Dilshod.")
    save_message(conv1, "user", "Boshim og'riyapti.")
    summary1 = build_conversation_summary(conv1)
    close_conversation(conv1, summary=summary1)

    conv2 = container.conversations.get_or_create_active_conversation(user_id)
    assert conv2 != conv1
    save_message(conv2, "user", "Salom, yana murojaat qilyapman.")

    context = load_conversation_context(user_id, conversation_id=conv2)
    assert context.context_instructions is not None
    assert "Dilshod" in context.context_instructions or "Boshim" in context.context_instructions

    summaries = container.conversations.get_prior_conversation_summaries(
        user_id,
        exclude_conversation_id=conv2,
    )
    assert len(summaries) >= 1

    print("Phase 2 Step 2.8 OK: closed conversation summaries recalled in new thread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
