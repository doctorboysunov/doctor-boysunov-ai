"""Wait for a real Telegram voice message and verify admin voice pipeline in logs."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DOCTOR_ID = 7898074891
LOG_FILE = ROOT / "data" / "bot_debug.log"


async def send_prompt() -> None:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": DOCTOR_ID,
                "text": (
                    "Voice fix deployed. Please send a voice message saying:\n"
                    "\"Ali Valiyev, telefon 701041101\""
                ),
            },
        )


def wait_for_voice_success(timeout_sec: int = 120) -> bool:
    start = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not LOG_FILE.exists():
            time.sleep(2)
            continue
        tail = LOG_FILE.read_text(encoding="utf-8", errors="replace")[start:]
        if "voice_patient_processed" in tail and "7898074891" in tail:
            return True
        if "voice_transcript=" in tail and "Ali Valiyev" in tail:
            return True
        time.sleep(2)
    return False


async def main() -> int:
    await send_prompt()
    print("Prompt sent. Waiting up to 120s for voice message in bot logs...")
    if wait_for_voice_success():
        print("OK: real Telegram voice pipeline succeeded")
        return 0
    print("FAIL: no voice success log yet")
    if LOG_FILE.exists():
        print(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2500:])
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
