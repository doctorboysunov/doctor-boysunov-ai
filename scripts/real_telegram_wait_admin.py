"""Send live Telegram test prompt and verify admin-mode log entry."""

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

DOCTOR_TELEGRAM_ID = 7898074891
LOG_FILE = ROOT / "data" / "bot_debug.log"
TEST_TEXT = "Ali Valiyev 701041101"


async def send_prompt() -> bool:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": DOCTOR_TELEGRAM_ID,
                "text": (
                    "Admin mode fix applied.\n"
                    "Please send exactly:\n"
                    "Ali Valiyev 701041101"
                ),
            },
        )
        payload = response.json()
    if not payload.get("ok"):
        print("sendMessage failed:", payload.get("description", payload))
        return False
    print("OK: prompt sent to doctor chat")
    return True


def wait_for_admin_patient_creation(timeout_sec: int = 90) -> bool:
    if not LOG_FILE.exists():
        print("FAIL: log file missing")
        return False

    start_size = LOG_FILE.stat().st_size
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        new_part = text[start_size:] if len(text) > start_size else text[-4000:]
        if (
            "telegram_user_id=7898074891 is_admin=True selected_mode=doctor_admin" in new_part
            and TEST_TEXT in new_part
            and "doctor_admin_mode" in new_part
        ):
            print("OK: admin mode log detected for doctor message")
            return True
        if "Patient created" in new_part and "7898074891" in new_part:
            print("OK: patient creation log detected")
            return True
        time.sleep(2)

    print("FAIL: timed out waiting for admin-mode handling in logs")
    print("--- log tail ---")
    print(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-3000:])
    return False


async def main() -> int:
    if not await send_prompt():
        return 1
    print("Waiting up to 90s for doctor to send test message...")
    return 0 if wait_for_admin_patient_creation() else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
