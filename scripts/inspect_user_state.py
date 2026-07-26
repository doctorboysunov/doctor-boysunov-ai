"""Inspect registration/location state for a Telegram user in clinic.db."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "clinic.db"


def main() -> None:
    telegram_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7898074891
    print(f"database={DB} exists={DB.exists()}")
    if not DB.exists():
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    print("\n=== users ===")
    users = conn.execute(
        "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
    ).fetchall()
    for row in users:
        print(dict(row))
    if not users:
        print("(none)")
        return

    user_id = users[0]["id"]

    print("\n=== admin_sessions ===")
    try:
        rows = conn.execute("SELECT * FROM admin_sessions").fetchall()
        for row in rows:
            print(dict(row))
        if not rows:
            print("(empty table)")
    except sqlite3.OperationalError as exc:
        print(f"table missing: {exc}")

    print("\n=== patient_profiles (location fields) ===")
    profile = conn.execute(
        "SELECT id, user_id, country, region, district, address, latitude, longitude, city_region "
        "FROM patient_profiles WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if profile:
        d = dict(profile)
        print(d)
        has_location = bool(d.get("country") and d.get("region") and d.get("district"))
        print(f"has_location_stored={has_location}")
    else:
        print("(no profile)")

    print("\n=== conversations ===")
    convs = conn.execute(
        "SELECT id, status, created_at, updated_at FROM conversations WHERE user_id=? ORDER BY id",
        (user_id,),
    ).fetchall()
    for row in convs:
        print(dict(row))

    if convs:
        cid = convs[-1]["id"]
        print(f"\n=== last 20 messages (conversation_id={cid}) ===")
        msgs = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 20",
            (cid,),
        ).fetchall()
        for row in reversed(msgs):
            d = dict(row)
            content = d.get("content") or ""
            d["content"] = content[:240]
            print(d)


if __name__ == "__main__":
    main()
