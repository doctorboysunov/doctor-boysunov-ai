"""Telegram voice message pipeline verification."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_voice_telegram.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["ADMIN_TELEGRAM_IDS"] = "7898074891"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "voice-test-token")
os.environ.setdefault("OPENAI_API_KEY", "voice-test-key")

sys.path.insert(0, str(ROOT))

from importlib import reload  # noqa: E402

import app.config as app_config  # noqa: E402
import app.settings as app_settings  # noqa: E402

app_settings.get_settings.cache_clear()
reload(app_settings)
reload(app_config)

from app.db.connection import init_db  # noqa: E402
from app.domain.admin_conversation_state import enter_patient_registration_mode  # noqa: E402
from app.handlers.patient_intake import handle_patient_voice  # noqa: E402
from app.services.patient_intake.extraction import extract_patient_from_text  # noqa: E402


class TestRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[tuple[str, str]] = []

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append((name, detail or "failed"))


class FakeUser:
    id = 7898074891
    username = "dr_Sohibnazar"
    full_name = "Sohibnazar Boysunov"


class FakeVoice:
    file_id = "voice-file-id"


class FakeMessage:
    def __init__(self) -> None:
        self.text = ""
        self.voice = FakeVoice()
        self.audio = None
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self) -> None:
        self.effective_user = FakeUser()
        self.message = FakeMessage()


class FakeBot:
    async def get_file(self, file_id: str):
        assert file_id == "voice-file-id"
        file_obj = MagicMock()
        file_obj.file_path = f"voice/{file_id}.oga"
        file_obj.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake-ogg-bytes"))
        return file_obj


class FakeContext:
    bot = FakeBot()
    user_data: dict = {}


def main() -> None:
    runner = TestRunner()
    init_db()

    transcript = "Ali Valiyev, telefon 701041101"
    extracted = extract_patient_from_text(transcript)
    runner.check("transcript_extracts", extracted is not None, repr(extracted))
    if extracted:
        runner.check("transcript_name", extracted.full_name == "Ali Valiyev", extracted.full_name)
        runner.check(
            "transcript_phone",
            extracted.phone_number == "+998701041101",
            extracted.phone_number,
        )

    async def run_handler() -> str:
        with patch(
            "app.handlers.patient_intake.transcribe_audio",
            return_value=transcript,
        ):
            ctx = FakeContext()
            enter_patient_registration_mode(ctx, admin_telegram_id=7898074891)
            update = FakeUpdate()
            await handle_patient_voice(update, ctx)
            return update.message.reply_text.await_args.args[0]

    reply = asyncio.run(run_handler())
    runner.check("handler_uses_bot_get_file", True, "")
    runner.check("confirmation_has_patient_id", "Patient ID" in reply, reply)
    runner.check("confirmation_has_name", "Ali Valiyev" in reply, reply)
    runner.check("confirmation_has_phone", "+998701041101" in reply, reply)
    runner.check("handler_replied_once", "Patient" in reply or "already exists" in reply.lower(), reply)

    async def run_download_error() -> str:
        class BrokenBot:
            async def get_file(self, file_id: str):
                raise RuntimeError("download failed")

        ctx = FakeContext()
        ctx.bot = BrokenBot()
        update = FakeUpdate()
        with patch(
            "app.handlers.patient_intake.transcribe_audio",
            return_value=transcript,
        ):
            await handle_patient_voice(update, ctx)
            return update.message.reply_text.await_args.args[0]

    error_reply = asyncio.run(run_download_error())
    runner.check("download_error_message", "yuklab bo'lmadi" in error_reply.lower(), error_reply)

    print()
    print("=" * 72)
    print(f"VOICE TELEGRAM VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed:
            print(f"FAIL | {name} | {detail}")
        raise SystemExit(1)
    print("Voice pipeline OK")
    print("=" * 72)


if __name__ == "__main__":
    main()
