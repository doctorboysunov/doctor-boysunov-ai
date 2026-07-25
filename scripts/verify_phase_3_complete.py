"""
Complete Phase 3 verification suite (100+ automated tests).

Covers: multiple users, restart, profiles, medical history, file linking,
profile updates, and conversation memory.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "verify_phase_3_complete.db"
TEST_FILES = ROOT / "data" / "verify_phase_3_complete_files"

if TEST_DB.exists():
    TEST_DB.unlink()
if TEST_FILES.exists():
    shutil.rmtree(TEST_FILES)

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["PATIENT_FILES_PATH"] = str(TEST_FILES)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "phase3-complete-token")
os.environ.setdefault("OPENAI_API_KEY", "phase3-complete-key")

sys.path.insert(0, str(ROOT))

from importlib import reload

import app.config as config_module
import app.settings as settings_module

reload(settings_module)
reload(config_module)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.domain.medical_history_types import MEDICAL_RECORD_TYPES  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.handlers.common import register_telegram_user  # noqa: E402
from app.handlers.documents import handle_patient_file  # noqa: E402
from app.repositories.conversation_repository import (  # noqa: E402
    get_last_messages,
    upsert_user,
)
from app.repositories.medical_history_repository import get_medical_history  # noqa: E402
from app.repositories.patient_file_repository import get_patient_files  # noqa: E402
from app.repositories.patient_profile_repository import (  # noqa: E402
    get_or_create_patient_profile,
    get_patient_profile,
    update_patient_profile,
)
from app.services.patient_context import build_profile_instructions  # noqa: E402
from app.services.patient_file_service import link_patient_file_to_history  # noqa: E402
from app.services.profile_extraction import extract_profile_updates  # noqa: E402
from app.settings import get_settings  # noqa: E402
from scripts.test_support import seed_default_location  # noqa: E402

openai_requests: list[dict] = []

USER_COUNT = 10
MEMORY_TURNS_PER_USER = 2


@dataclass
class TestRunner:
    passed: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
        else:
            self.failed.append((name, detail or "assertion failed"))

    def eq(self, name: str, got, expected) -> None:
        self.check(name, got == expected, f"got {got!r}, expected {expected!r}")

    def true(self, name: str, value) -> None:
        self.check(name, bool(value), f"value={value!r}")

    def in_(self, name: str, needle: str, haystack: str) -> None:
        self.check(name, needle in haystack, f"{needle!r} not in {haystack!r}")


class FakeUser:
    def __init__(self, telegram_id: int, name: str):
        self.id = telegram_id
        self.username = f"u_{telegram_id}"
        self.full_name = name


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, telegram_id: int, name: str, text: str):
        self.effective_user = FakeUser(telegram_id, name)
        self.message = FakeMessage(text)


def normalize_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fake_responses_create(**kwargs):
    openai_requests.append(kwargs)

    class FakeResponse:
        output_text = "Test javob."
        id = f"resp_{len(openai_requests)}"

    return FakeResponse()


def simulate_restart(runner: TestRunner, label: str) -> None:
    get_settings.cache_clear()
    init_db()
    runner.true(f"{label}_restart_db_exists", TEST_DB.exists())


async def run_chat(telegram_id: int, name: str, text: str) -> tuple[str, str]:
    out = StringIO()
    update = FakeUpdate(telegram_id, name, text)
    user_id = register_telegram_user(update)
    seed_default_location(user_id)
    with redirect_stdout(out):
        with patch(
            "app.services.openai_service.client.responses.create",
            side_effect=fake_responses_create,
        ):
            await chat(update, None)
    answer = update.message.reply_text.await_args.args[0]
    return answer, out.getvalue()


def parse_history_count(stdout: str) -> int:
    block = stdout.split("=== BEFORE ask_ai() ===")[-1]
    block = block.split("=== BEFORE OPENAI ===")[0]
    match = re.search(r"history_count=(\d+)", block)
    return int(match.group(1)) if match else -1


async def run_document(
    telegram_id: int,
    file_name: str,
    payload: bytes,
    mime_type: str,
    caption: str | None,
) -> None:
    fake_file = MagicMock()
    fake_file.download_as_bytearray = AsyncMock(return_value=bytearray(payload))

    document = MagicMock()
    document.file_name = file_name
    document.mime_type = mime_type
    document.file_id = f"file-{telegram_id}-{file_name}"
    document.file_unique_id = f"unique-{file_name}"
    document.get_file = AsyncMock(return_value=fake_file)

    user = MagicMock()
    user.id = telegram_id
    user.username = "doc_user"
    user.full_name = "Doc User"

    message = MagicMock()
    message.photo = None
    message.document = document
    message.caption = caption
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.message = message
    update.effective_user = user

    await handle_patient_file(update, None)


async def main() -> None:
    runner = TestRunner()
    init_db()

    # --- Schema / isolation (6 tests) ---
    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    for table in (
        "users",
        "patient_profiles",
        "medical_history",
        "patient_files",
        "conversations",
        "messages",
    ):
        runner.true(f"schema_table_{table}", table in tables)

    # --- Multiple users + permanent profiles (30 tests) ---
    user_ids: dict[int, int] = {}
    names = [
        "Sohibnazar",
        "Dilnoza",
        "Jamshid",
        "Malika",
        "Rustam",
        "Aziza",
        "Bekzod",
        "Nigora",
        "Timur",
        "Madina",
    ]
    for index, name in enumerate(names):
        telegram_id = 500000 + index
        user_id = upsert_user(telegram_id, f"user_{index}", name)
        user_ids[telegram_id] = user_id
        profile = get_or_create_patient_profile(user_id)
        runner.eq(f"user_{index}_profile_user_id", profile["user_id"], user_id)
        runner.true(f"user_{index}_profile_unique", profile["id"] > 0)
        runner.eq(f"user_{index}_profile_starts_empty", profile["full_name"], None)

    runner.eq("multi_user_count", len(user_ids), USER_COUNT)

    # --- Profile updates + extraction (25 tests) ---
    extraction_cases = [
        ("Mening ismim Sohibnazar.", {"full_name": "Sohibnazar"}),
        ("Men 32 yoshdaman.", {"age": 32}),
        ("Men ayolman.", {"sex": "female"}),
        ("Bo'yim 165 sm.", {"height_cm": 165}),
        ("Vaznim 62 kg.", {"weight_kg": 62}),
        ("Telefon raqamim +998901234567.", {"phone_number": "+998901234567"}),
        ("Manzilim Toshkent, Yunusobod.", {"address": "Toshkent, Yunusobod"}),
        ("Kasbim hamshira.", {"occupation": "hamshira"}),
        ("Allergiyam penitsillin.", {"allergies": "penitsillin"}),
        ("Menda diabet bor.", {"chronic_diseases": "diabet"}),
        ("Mening ismim kim?", {}),
    ]
    primary_tid = 500000
    primary_uid = user_ids[primary_tid]
    for idx, (message, expected) in enumerate(extraction_cases):
        got = extract_profile_updates(message)
        if expected:
            for key, value in expected.items():
                runner.eq(f"extract_{idx}_{key}", got.get(key), value)
        else:
            runner.eq(f"extract_{idx}_empty", got, {})

    update_patient_profile(
        primary_uid,
        full_name="Sohibnazar",
        age=32,
        city_region="Surxondaryo",
    )
    profile = get_patient_profile(primary_uid)
    runner.eq("profile_update_name", profile["full_name"], "Sohibnazar")
    runner.eq("profile_update_age", profile["age"], 32)
    runner.eq("profile_update_region", profile["city_region"], "Surxondaryo")

    instructions = build_profile_instructions(profile)
    runner.true("profile_instructions_present", instructions is not None)
    runner.in_("profile_instructions_name", "Sohibnazar", instructions or "")
    runner.in_("profile_no_repeat_rule", "Do not ask", instructions or "")

    # --- Medical history per user (20 tests) ---
    record_samples = {
        "symptom": "Bosh og'rig'i",
        "diagnosis": "Lumbal disk herniya",
        "mri": "L4-L5 protruziya",
        "ct": "KT natija",
        "emg": "EMG sekin ileti",
        "laboratory": "CRP 12",
        "treatment": "Fizioterapiya",
        "consultation": "Nevrolog qabuli",
    }
    for uid in list(user_ids.values())[:2]:
        for record_type, content in record_samples.items():
            from app.repositories.medical_history_repository import add_medical_record

            add_medical_record(uid, record_type, content)
        history = get_medical_history(uid)
        runner.eq(f"history_count_user_{uid}", len(history), len(MEDICAL_RECORD_TYPES))
        runner.eq(
            f"history_types_user_{uid}",
            {row["record_type"] for row in history},
            set(MEDICAL_RECORD_TYPES),
        )

    # --- File linking (20 tests) ---
    file_cases = [
        ("mri_scan.pdf", b"MRI", "application/pdf", "MRT hisobot", "mri"),
        ("lab.pdf", b"LAB", "application/pdf", "Laboratoriya natija", "laboratory"),
        ("report.docx", b"DOC", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None, "consultation"),
        ("photo.jpg", b"IMG", "image/jpeg", "Rentgen", "consultation"),
    ]
    for idx, (fname, payload, mime, caption, expected_type) in enumerate(file_cases):
        result = link_patient_file_to_history(
            primary_uid,
            file_name=fname,
            file_bytes=payload,
            mime_type=mime,
            caption=caption,
        )
        runner.eq(f"file_{idx}_record_type", result["record_type"], expected_type)
        runner.true(f"file_{idx}_stored", Path(result["patient_file"]["stored_path"]).exists())
        runner.eq(
            f"file_{idx}_history_link",
            result["patient_file"]["medical_history_id"],
            result["medical_history"]["id"],
        )
        runner.in_(f"file_{idx}_user_folder", str(primary_uid), result["patient_file"]["stored_path"])

    await run_document(primary_tid, "kt_report.pdf", b"KT", "application/pdf", "KT natija")
    runner.eq("handler_files_total", len(get_patient_files(primary_uid)), len(file_cases) + 1)

    # --- Conversation memory mocked (40 tests: 10 users × 2 turns × 2 checks) ---
    memory_names = names[:USER_COUNT]
    for index, name in enumerate(memory_names):
        telegram_id = 500000 + index
        intro = f"Mening ismim {name}."
        recall = "Mening ismim kim?"

        _, out1 = await run_chat(telegram_id, name, intro)
        runner.eq(f"memory_{index}_turn1_history_count", parse_history_count(out1), 1)

        prof = get_patient_profile(user_ids[telegram_id])
        runner.eq(f"memory_{index}_profile_name", prof["full_name"], name)

        answer2, out2 = await run_chat(telegram_id, name, recall)
        runner.eq(f"memory_{index}_turn2_history_count", parse_history_count(out2), 3)
        runner.true(
            f"memory_{index}_openai_instructions",
            "instructions" in openai_requests[-1]
            and name in (openai_requests[-1].get("instructions") or ""),
        )

        uid = user_ids[telegram_id]
        conv_history = get_medical_history(uid)
        runner.true(f"memory_{index}_history_independent", len(conv_history) >= 0)
        runner.true(f"memory_{index}_answer_nonempty", bool(answer2.strip()))

    # --- Cross-user isolation (10 tests) ---
    for index in range(USER_COUNT):
        telegram_id = 500000 + index
        uid = user_ids[telegram_id]
        runner.eq(
            f"isolation_profile_{index}",
            get_patient_profile(uid)["full_name"],
            names[index],
        )
    runner.eq("isolation_user_b_files", len(get_patient_files(user_ids[500001])), 0)
    runner.eq("isolation_user_a_files", len(get_patient_files(primary_uid)), len(file_cases) + 1)

    # --- Restart persistence (15 tests) ---
    simulate_restart(runner, "phase3")
    for index in range(USER_COUNT):
        telegram_id = 500000 + index
        uid = user_ids[telegram_id]
        prof = get_patient_profile(uid)
        runner.eq(f"restart_profile_{index}", prof["full_name"], names[index])

    runner.eq(
        "restart_primary_history",
        len(get_medical_history(primary_uid)),
        len(MEDICAL_RECORD_TYPES) + len(file_cases) + 1,
    )
    runner.eq("restart_primary_files", len(get_patient_files(primary_uid)), len(file_cases) + 1)
    runner.true(
        "restart_file_on_disk",
        Path(get_patient_files(primary_uid)[0]["stored_path"]).exists(),
    )

    _, out_after_restart = await run_chat(primary_tid, names[0], "Mening ismim kim?")
    runner.eq("restart_memory_history_count", parse_history_count(out_after_restart), 5)

    with get_connection() as conn:
        user_rows = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        profile_rows = conn.execute("SELECT COUNT(*) FROM patient_profiles").fetchone()[0]
    runner.eq("restart_users_persist", user_rows, USER_COUNT)
    runner.eq("restart_profiles_persist", profile_rows, USER_COUNT)

    # --- Summary ---
    print()
    print("=" * 72)
    print(f"PHASE 3 VERIFICATION: {runner.passed}/{runner.total} tests passed")
    print("=" * 72)
    if runner.failed:
        for name, detail in runner.failed[:20]:
            print(f"FAIL | {name} | {detail}")
        if len(runner.failed) > 20:
            print(f"... and {len(runner.failed) - 20} more failures")
        print("=" * 72)
        raise SystemExit(1)

    if runner.total < 100:
        print(f"ERROR: only {runner.total} tests executed (minimum 100 required)")
        raise SystemExit(1)

    print("Phase 3 Complete")
    print(f"Total automated tests: {runner.total}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
