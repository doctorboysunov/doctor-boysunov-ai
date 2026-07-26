"""End-to-end live Telegram test for Phase 10 consultation engine."""

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
CONSULTATION_PROBE = "Boshim og'riyapti"
ADMIN_PROBE = "Salom"
POLL_SECONDS = 90


def head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


async def tg(method: str, **payload) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=40.0) as client:
        if payload:
            response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        else:
            response = await client.get(f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}")
            if method == "github_commit":
                response = await client.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}",
                    headers={"Accept": "application/vnd.github+json"},
                )
            else:
                response = await client.get(f"https://api.telegram.org/bot{token}/{method}")
        return {"status_code": response.status_code, "json": response.json() if response.content else {}}


async def wait_deploy(sha: str) -> tuple[bool, str]:
    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}",
                headers={"Accept": "application/vnd.github+json"},
            )
            if response.status_code == 200:
                remote = response.json()["sha"]
                if remote.startswith(sha[:7]) or sha.startswith(remote[:7]):
                    return True, remote
        await asyncio.sleep(5)
    return False, ""


async def telegram_call(method: str, payload: dict | None = None) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    async with httpx.AsyncClient(timeout=40.0) as client:
        if payload is None:
            response = await client.get(f"https://api.telegram.org/bot{token}/{method}")
        else:
            response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        body = response.json() if response.content else {}
        return {"http_status": response.status_code, "body": body}


async def deployment_statuses(deployment_id: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/deployments/{deployment_id}/statuses",
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code != 200:
            return []
        return response.json()


async def latest_deployment_for_sha(sha: str) -> dict | None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/deployments",
            params={"per_page": 10},
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code != 200:
            return None
        for item in response.json():
            if item.get("sha", "").startswith(sha[:7]):
                return item
    return None


async def wait_railway_success(sha: str) -> tuple[bool, str]:
    deadline = time.time() + POLL_SECONDS
    detail = "no deployment found"
    while time.time() < deadline:
        deployment = await latest_deployment_for_sha(sha)
        if deployment:
            statuses = await deployment_statuses(deployment["id"])
            if statuses:
                latest = statuses[0]
                state = latest.get("state")
                detail = f"deployment={deployment['id']} state={state} desc={latest.get('description','')}"
                if state == "success":
                    return True, detail
                if state in {"failure", "error"}:
                    return False, detail
        await asyncio.sleep(8)
    return False, detail


async def probe_live_reply(chat_id: int, send_text: str, wait_sec: int = 20) -> dict:
    """Send user message via getUpdates loop is impossible while Railway polls.
    Instead send bot->user ping and return metadata. Live reply must be observed in Telegram app."""
    sent = await telegram_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": f"🧪 Live probe: please send exactly this message to the bot now:\n{send_text}",
        },
    )
    await asyncio.sleep(wait_sec)
    return {
        "instruction_sent": sent["body"].get("ok", False),
        "instruction_message_id": (sent["body"].get("result") or {}).get("message_id"),
        "note": "Bot reply must be checked in Telegram client; Bot API cannot read outgoing chat history.",
    }


async def main() -> None:
    if os.environ.get("RUN_LIVE_TELEGRAM_TESTS") != "1":
        print("SKIP: verify_live_phase_10 (set RUN_LIVE_TELEGRAM_TESTS=1 for deploy/live checks)")
        return

    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN missing")
        sys.exit(1)

    sha = head_sha()
    report: dict = {"commit": sha, "checks": []}

    deploy_visible, remote_sha = await wait_deploy(sha)
    report["remote_sha"] = remote_sha
    report["checks"].append(("github_commit_on_branch", deploy_visible, remote_sha[:12]))

    railway_ok, railway_detail = await wait_railway_success(sha)
    report["checks"].append(("railway_deployment", railway_ok, railway_detail))

    me = await telegram_call("getMe")
    username = (me["body"].get("result") or {}).get("username")
    report["checks"].append(("telegram_getMe", me["body"].get("ok", False), username))

    webhook = await telegram_call("getWebhookInfo")
    webhook_url = (webhook["body"].get("result") or {}).get("url") or ""
    report["checks"].append(("telegram_polling", webhook_url == "", webhook_url or "polling"))

    conflict = await telegram_call("getUpdates", {"timeout": 0, "limit": 1})
    conflict_ok = conflict["http_status"] == 409 or (
        conflict["body"].get("ok") and conflict["body"].get("result") == []
    )
    report["checks"].append(
        (
            "single_poller_or_idle",
            conflict_ok,
            f"http={conflict['http_status']} body={json.dumps(conflict['body'])[:120]}",
        )
    )

    admin_probe = await probe_live_reply(ADMIN_CHAT_ID, ADMIN_PROBE, wait_sec=8)
    report["admin_salom_probe"] = admin_probe
    report["checks"].append(("admin_probe_instruction_sent", admin_probe["instruction_sent"], ADMIN_PROBE))

    patient_id = os.environ.get("LIVE_TEST_PATIENT_TELEGRAM_ID")
    if patient_id:
        patient_probe = await probe_live_reply(int(patient_id), CONSULTATION_PROBE, wait_sec=12)
        report["patient_consultation_probe"] = patient_probe
        report["checks"].append(
            ("patient_probe_instruction_sent", patient_probe["instruction_sent"], CONSULTATION_PROBE)
        )
    else:
        report["checks"].append(
            (
                "patient_consultation_live",
                False,
                "Set LIVE_TEST_PATIENT_TELEGRAM_ID for automated patient-side instruction",
            )
        )

    print("\n=== LIVE TELEGRAM TEST REPORT (Phase 10) ===")
    print(json.dumps({"commit": sha, "remote_sha": remote_sha, "bot": username}, indent=2))
    failed = 0
    for name, ok, detail in report["checks"]:
        status = "PASS" if ok else "WARN" if name.startswith("patient_") else ("PASS" if ok else "FAIL")
        if not ok and not name.startswith("patient_"):
            failed += 1
            status = "FAIL"
        print(f"{status} | {name} | {detail}")

    if report.get("admin_salom_probe"):
        print("\nAdmin probe:", json.dumps(report["admin_salom_probe"], indent=2))
    if report.get("patient_consultation_probe"):
        print("Patient probe:", json.dumps(report["patient_consultation_probe"], indent=2))

    print(f"\nAutomated live infra checks failed: {failed}")
    print(
        "Manual confirmation in Telegram:\n"
        f"- Admin ({ADMIN_CHAT_ID}): send '{ADMIN_PROBE}' -> expect Medical AI greeting\n"
        f"- Patient account: send '{CONSULTATION_PROBE}' -> expect ONE consultation question"
    )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
