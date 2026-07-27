"""Poll GitHub deployments for Railway status on clean-main."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPO = "doctorboysunov/doctor-boysunov-ai"
BRANCH = "clean-main"
POLL_SECONDS = 180


def local_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()


async def branch_sha(client: httpx.AsyncClient) -> str:
    r = await client.get(
        f"https://api.github.com/repos/{REPO}/commits/{BRANCH}",
        headers={"Accept": "application/vnd.github+json"},
    )
    r.raise_for_status()
    return r.json()["sha"]


async def latest_deployment(client: httpx.AsyncClient, sha: str) -> dict | None:
    r = await client.get(
        f"https://api.github.com/repos/{REPO}/deployments",
        params={"per_page": 15},
        headers={"Accept": "application/vnd.github+json"},
    )
    if r.status_code != 200:
        return None
    for item in r.json():
        if item.get("sha", "").startswith(sha[:7]):
            return item
    return None


async def latest_status(client: httpx.AsyncClient, deployment_id: int) -> dict | None:
    r = await client.get(
        f"https://api.github.com/repos/{REPO}/deployments/{deployment_id}/statuses",
        headers={"Accept": "application/vnd.github+json"},
    )
    if r.status_code != 200 or not r.json():
        return None
    return r.json()[0]


async def wait_success(sha: str) -> tuple[bool, str]:
    deadline = time.time() + POLL_SECONDS
    detail = "no deployment found"
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() < deadline:
            deployment = await latest_deployment(client, sha)
            if deployment:
                status = await latest_status(client, deployment["id"])
                if status:
                    state = status.get("state")
                    detail = (
                        f"deployment_id={deployment['id']} state={state} "
                        f"desc={status.get('description', '')} at={status.get('created_at', '')}"
                    )
                    if state == "success":
                        return True, detail
                    if state in {"failure", "error"}:
                        return False, detail
            await asyncio.sleep(8)
    return False, detail


async def main() -> None:
    sha = local_sha()
    async with httpx.AsyncClient(timeout=30.0) as client:
        remote = await branch_sha(client)
    print(f"local_sha={sha}")
    print(f"remote_sha={remote}")
    if not (remote.startswith(sha[:7]) or sha.startswith(remote[:7])):
        print("FAIL: GitHub branch does not match local HEAD")
        sys.exit(1)
    ok, detail = await wait_success(sha)
    print(f"railway_ok={ok}")
    print(f"detail={detail}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    asyncio.run(main())
