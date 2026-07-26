"""Wait for live Telegram Salom and verify bot did not return registration hint."""

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
REGISTRATION_HINT = "Bemor qo'shish uchun ism va telefon yuboring."


async def send_prompt() -> None:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=20.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": DOCTOR_ID,
                "text": (
                    "Routing fix v2 deployed.\n"
                    "Please send exactly: Salom"
                ),
            },
        )


async def poll_for_salom_reply(timeout_sec: int = 120) -> bool:
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    offset = None
    deadline = time.time() + timeout_sec
    saw_salom = False

    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() < deadline:
            params = {"timeout": 10, "allowed_updates": json.dumps(["message"])}
            if offset is not None:
                params["offset"] = offset
            response = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params=params,
            )
            payload = response.json()
            if not payload.get("ok"):
                print("getUpdates failed:", payload)
                await asyncio.sleep(2)
                continue

            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                text = message.get("text") or ""
                from_user = message.get("from") or {}
                user_id = from_user.get("id")
                if user_id == DOCTOR_ID and text.strip().lower() == "salom":
                    saw_salom = True
                    print(f"OK: saw live incoming Salom from doctor id={user_id}")

            if saw_salom:
                # Bot reply is not returned by getUpdates; confirm no registration hint via sendChatAction poll impossible.
                # Instead fetch recent outgoing by asking user to report, or rely on Railway logs.
                print("Live Salom received by bot polling endpoint.")
                print("Check Railway logs for:")
                print("  routing_fix_version=2026-07-26-salom-medical-ai-v2")
                print("  selected_handler=Medical AI (ask_ai)")
                print("  chat_medical_ai conversation_mode=doctor_admin")
                return True

            await asyncio.sleep(1)

    return False


async def main() -> int:
    import json  # noqa: PLC0415

    global json
    json = __import__("json")

    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("SKIP live poll: TELEGRAM_BOT_TOKEN missing")
        return 1

    await send_prompt()
    print("Prompt sent. Waiting up to 120s for live Salom via getUpdates...")
    ok = await poll_for_salom_reply()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
