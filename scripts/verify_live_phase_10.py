"""Live Telegram + deployment verification for Phase 10 consultation engine."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

ADMIN_CHAT_ID = int(os.environ.get("ADMIN_TELEGRAM_IDS", "7898074891").split(",")[0])
GITHUB_REPO = "doctorboysunov/doctor-boysunov-ai"
GITHUB_BRANCH = "clean-main"
LIVE_TEST_MESSAGE = "Boshim og'riyapti"
PATIENT_TEST_TELEGRAM_ID = int(os.environ.get("LIVE_TEST_PATIENT_TELEGRAM_ID", "0") or "0")


async def telegram_get(path: str, **params) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/{path}", params=params)
        response.raise_for_status()
        return response.json()


async def telegram_post(path: str, payload: dict) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"https://api.telegram.org/bot{token}/{path}", json=payload)
        response.raise_for_status()
        return response.json()


def local_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def remote_branch_sha() -> str:
    result = subprocess.run(
        ["git", "ls-remote", "origin", f"refs/heads/{GITHUB_BRANCH}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    line = result.stdout.strip().split("\t")[0]
    return line


async def github_latest_commit_sha() -> str:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        data = response.json()
        return data["sha"]


async def wait_for_github_sha(expected_sha: str, timeout_sec: int = 180) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            remote_sha = await github_latest_commit_sha()
            if remote_sha.startswith(expected_sha[:7]) or expected_sha.startswith(remote_sha[:7]):
                return True
        except Exception as exc:
            print(f"github poll error: {exc}")
        await asyncio.sleep(5)
    return False


async def notify_admin(text: str) -> None:
    await telegram_post(
        "sendMessage",
        {"chat_id": ADMIN_CHAT_ID, "text": text},
    )


async def run_live_bot_checks() -> dict:
    results: dict = {"checks": []}

    me = await telegram_get("getMe")
    results["bot"] = me["result"]
    results["checks"].append(("telegram_getMe", me.get("ok", False), me["result"].get("username")))

    webhook = await telegram_get("getWebhookInfo")
    webhook_url = webhook["result"].get("url") or ""
    results["checks"].append(("telegram_polling_mode", webhook_url == "", webhook_url or "polling"))

    head = local_head_sha()
    pushed = remote_branch_sha()
    results["local_sha"] = head
    results["remote_sha"] = pushed
    results["checks"].append(("github_push_visible", head.startswith(pushed[:7]) or pushed.startswith(head[:7]), pushed[:12]))

    github_ok = await wait_for_github_sha(head, timeout_sec=120)
    results["checks"].append(("github_branch_updated", github_ok, head[:12]))

    await notify_admin(
        "Phase 10 live test deployed.\n"
        "If you have a patient Telegram account, send exactly:\n"
        f"{LIVE_TEST_MESSAGE}\n\n"
        "Expected: one consultation question (not a full question list).\n"
        "Admin accounts still use Medical AI, not the consultation engine."
    )
    results["checks"].append(("admin_notified", True, str(ADMIN_CHAT_ID)))

    if PATIENT_TEST_TELEGRAM_ID:
        await notify_admin(
            f"Patient live test account configured: {PATIENT_TEST_TELEGRAM_ID}. "
            f"Ask that account to send: {LIVE_TEST_MESSAGE}"
        )
        results["checks"].append(("patient_test_id_configured", True, str(PATIENT_TEST_TELEGRAM_ID)))
    else:
        results["checks"].append(
            (
                "patient_live_message",
                False,
                "Set LIVE_TEST_PATIENT_TELEGRAM_ID in .env for automated patient-side live test",
            )
        )

    admin_probe = await telegram_post(
        "sendMessage",
        {"chat_id": ADMIN_CHAT_ID, "text": "Salom"},
    )
    results["checks"].append(("admin_salom_probe_sent", admin_probe.get("ok", False), "bot can send to admin"))

    return results


def print_report(results: dict) -> int:
    print("\n=== LIVE PHASE 10 TEST REPORT ===")
    print(json.dumps({"bot": results.get("bot"), "local_sha": results.get("local_sha"), "remote_sha": results.get("remote_sha")}, indent=2))
    failed = 0
    for name, ok, detail in results["checks"]:
        status = "PASS" if ok else "FAIL"
        print(f"{status} | {name} | {detail}")
        if not ok:
            failed += 1
    print(f"\nSummary: {len(results['checks']) - failed}/{len(results['checks'])} live checks passed")
    if failed:
        print("Note: patient_live_message requires a non-admin Telegram account sending to the bot.")
        return 1
    return 0


async def main() -> None:
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN missing")
        sys.exit(1)
    results = await run_live_bot_checks()
    raise SystemExit(print_report(results))


if __name__ == "__main__":
    asyncio.run(main())
