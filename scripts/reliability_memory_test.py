"""
Reliability test: SQLite save, history load, OpenAI payload, and recall answer.

Runs 20 two-turn memory conversations, simulates bot restart, runs 20 again.
Every user message is verified across all four checks. Requires real OPENAI_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "reliability_memory_test.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "reliability-test-token")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import DATABASE_PATH  # noqa: E402
from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.chat import chat  # noqa: E402
from app.services import openai_service  # noqa: E402
from app.settings import get_settings  # noqa: E402

_original_create = openai_service.client.responses.create


@dataclass
class MessageCheck:
    phase: str
    test_id: int
    turn: int
    user_text: str
    expected_name: str | None = None
    sqlite_ok: bool = False
    history_ok: bool = False
    openai_ok: bool = False
    answer_ok: bool = False
    error: str = ""


@dataclass
class ConversationCase:
    test_id: int
    telegram_id: int
    name: str
    intro: str
    recall_question: str


CASES: list[ConversationCase] = [
    ConversationCase(1, 100001, "Sohibnazar", "Mening ismim Sohibnazar.", "Mening ismim kim?"),
    ConversationCase(2, 100002, "Xaknazar", "Mening ismim Xaknazar.", "Mening ismim nima?"),
    ConversationCase(3, 100003, "Aziza", "Mening ismim Aziza.", "Ismim nima?"),
    ConversationCase(4, 100004, "Jamshid", "Men Jamshidman.", "Mening ismim kim?"),
    ConversationCase(5, 100005, "Dilnoza", "Mening ismim Dilnoza.", "Menga ismimni ayt."),
    ConversationCase(6, 100006, "Rustam", "Ismim Rustam.", "Mening ismim nima?"),
    ConversationCase(7, 100007, "Malika", "Mening ismim Malika.", "Mening ismim kim?"),
    ConversationCase(8, 100008, "Bekzod", "Men Bekzodman.", "Ismim nima?"),
    ConversationCase(9, 100009, "Nigora", "Mening ismim Nigora.", "Mening ismim nima?"),
    ConversationCase(10, 100010, "Sardor", "Ismim Sardor.", "Mening ismim kim?"),
    ConversationCase(11, 100011, "Feruza", "Mening ismim Feruza.", "Menga ismimni ayt."),
    ConversationCase(12, 100012, "Ulugbek", "Men Ulugbekman.", "Mening ismim nima?"),
    ConversationCase(13, 100013, "Kamola", "Mening ismim Kamola.", "Mening ismim kim?"),
    ConversationCase(14, 100014, "Javohir", "Ismim Javohir.", "Ismim nima?"),
    ConversationCase(15, 100015, "Sevinch", "Mening ismim Sevinch.", "Mening ismim nima?"),
    ConversationCase(16, 100016, "Timur", "Men Timurman.", "Mening ismim kim?"),
    ConversationCase(17, 100017, "Madina", "Mening ismim Madina.", "Menga ismimni ayt."),
    ConversationCase(18, 100018, "Alisher", "Ismim Alisher.", "Mening ismim nima?"),
    ConversationCase(19, 100019, "Nilufar", "Mening ismim Nilufar.", "Mening ismim kim?"),
    ConversationCase(20, 100020, "Bobur", "Men Boburman.", "Ismim nima?"),
]

openai_requests: list[dict[str, Any]] = []
message_checks: list[MessageCheck] = []


class FakeUser:
    def __init__(self, telegram_id: int, name: str):
        self.id = telegram_id
        self.username = f"user_{telegram_id}"
        self.full_name = name


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUpdate:
    def __init__(self, telegram_id: int, name: str, text: str):
        self.effective_user = FakeUser(telegram_id, name)
        self.message = FakeMessage(text)


def capturing_create(*, model, input, **kwargs):
    payload = {"model": model, "input": input, **kwargs}
    openai_requests.append(payload)
    return _original_create(model=model, input=input, **kwargs)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"[''`ʻʼ\-]", "", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


def name_in_answer(name: str, answer: str) -> bool:
    return normalize(name) in normalize(answer)


def normalize_content(text: str) -> str:
    return re.sub(r"\s+", " ", normalize(text)).strip()


def extract_openai_contents(api_input: Any) -> list[str]:
    if isinstance(api_input, str):
        return [api_input]
    if isinstance(api_input, list):
        return [
            item.get("content", "")
            for item in api_input
            if isinstance(item, dict) and item.get("content")
        ]
    return []


def openai_input_contains_all(api_input: Any, texts: list[str]) -> tuple[bool, str]:
    contents = extract_openai_contents(api_input)
    normalized_fields = [normalize_content(c) for c in contents]
    combined = " ".join(normalized_fields)
    missing = []
    for text in texts:
        needle = normalize_content(text)
        if needle not in combined and not any(
            needle in field or field in needle for field in normalized_fields
        ):
            missing.append(text)
    if missing:
        serialized = json.dumps(api_input, ensure_ascii=False)
        return False, f"OpenAI input missing: {missing!r}. input={serialized!r}"
    return True, ""


def sqlite_has_message(conversation_id: int, content: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM messages
            WHERE conversation_id = ? AND role = 'user' AND content = ?
            """,
            (conversation_id, content),
        ).fetchone()
    return row is not None


def get_conversation_id(telegram_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT c.id
            FROM conversations c
            JOIN users u ON u.id = c.user_id
            WHERE u.telegram_id = ?
            ORDER BY c.id DESC
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()
    if row is None:
        raise AssertionError(f"No conversation for telegram_id={telegram_id}")
    return int(row[0])


def history_contents(history: list[dict[str, str]]) -> list[str]:
    return [m["content"] for m in history]


def parse_before_ask_ai(stdout: str) -> tuple[int, list[dict[str, str]]]:
    if "=== BEFORE ask_ai() ===" not in stdout:
        raise AssertionError("Missing BEFORE ask_ai() log from app/handlers/chat.py")
    block = stdout.split("=== BEFORE ask_ai() ===")[-1]
    block = block.split("=== OPENAI REQUEST ===")[0]
    count_match = re.search(r"history_count=(\d+)", block)
    history_match = re.search(r"history=(\[[\s\S]*\])", block)
    if not count_match or not history_match:
        raise AssertionError(f"Could not parse history from stdout block: {block!r}")
    history = json.loads(history_match.group(1))
    return int(count_match.group(1)), history


def verify_turn(
    *,
    phase: str,
    case: ConversationCase,
    turn: int,
    user_text: str,
    stdout: str,
    answer: str,
    request_index: int,
    expect_name_in_answer: bool,
    prior_user_text: str | None = None,
) -> MessageCheck:
    check = MessageCheck(
        phase=phase,
        test_id=case.test_id,
        turn=turn,
        user_text=user_text,
        expected_name=case.name if expect_name_in_answer else None,
    )

    try:
        conversation_id = get_conversation_id(case.telegram_id)

        if not sqlite_has_message(conversation_id, user_text):
            raise AssertionError(
                f"SQLite missing user message {user_text!r} "
                f"(app/handlers/chat.py save_message)"
            )
        check.sqlite_ok = True

        history_count, printed_history = parse_before_ask_ai(stdout)
        printed_contents = history_contents(printed_history)

        if user_text not in printed_contents:
            raise AssertionError(
                f"Current user message not in history at ask_ai time: "
                f"{printed_history!r}"
            )
        if turn == 1 and history_count != 1:
            raise AssertionError(f"Turn 1 expected history_count=1, got {history_count}")
        if turn == 2:
            if history_count != 3:
                raise AssertionError(
                    f"Turn 2 expected history_count=3, got {history_count}"
                )
            if prior_user_text and prior_user_text not in printed_contents:
                raise AssertionError(
                    f"Prior user message missing from history at ask_ai time: "
                    f"{prior_user_text!r} in {printed_history!r}"
                )
        check.history_ok = True

        if request_index >= len(openai_requests):
            raise AssertionError(
                f"No OpenAI request at index {request_index} "
                f"(app/services/openai_service.py ask_ai)"
            )
        api_input = openai_requests[request_index]["input"]
        ok, err = openai_input_contains_all(api_input, printed_contents)
        if not ok:
            raise AssertionError(err)
        check.openai_ok = True

        if expect_name_in_answer:
            if not name_in_answer(case.name, answer):
                raise AssertionError(
                    f"Expected name {case.name!r} in answer {answer!r}"
                )
        elif not answer.strip():
            raise AssertionError("Empty assistant answer on intro turn")
        check.answer_ok = True

    except AssertionError as exc:
        check.error = str(exc)

    message_checks.append(check)
    return check


async def run_turn(case: ConversationCase, text: str) -> tuple[str, str]:
    out = StringIO()
    with redirect_stdout(out):
        update = FakeUpdate(case.telegram_id, case.name, text)
        await chat(update, None)
    answer = update.message.reply_text.await_args.args[0]
    return answer, out.getvalue()


async def run_conversation(phase: str, case: ConversationCase) -> None:
    start_index = len(openai_requests)

    answer1, stdout1 = await run_turn(case, case.intro)
    check1 = verify_turn(
        phase=phase,
        case=case,
        turn=1,
        user_text=case.intro,
        stdout=stdout1,
        answer=answer1,
        request_index=start_index,
        expect_name_in_answer=False,
    )
    if check1.error:
        raise AssertionError(
            f"[{phase}] test #{case.test_id} turn 1 FAILED: {check1.error}"
        )

    answer2, stdout2 = await run_turn(case, case.recall_question)
    check2 = verify_turn(
        phase=phase,
        case=case,
        turn=2,
        user_text=case.recall_question,
        stdout=stdout2,
        answer=answer2,
        request_index=start_index + 1,
        expect_name_in_answer=True,
        prior_user_text=case.intro,
    )
    if check2.error:
        raise AssertionError(
            f"[{phase}] test #{case.test_id} turn 2 FAILED: {check2.error}\n"
            f"answer={answer2!r}"
        )


def simulate_bot_restart() -> None:
    """Persist DB, re-run startup path like app.main after process restart."""
    get_settings.cache_clear()
    init_db()
    with get_connection() as conn:
        conn.execute("SELECT 1").fetchone()


def print_summary() -> None:
    total = len(message_checks)
    passed = sum(
        1
        for c in message_checks
        if c.sqlite_ok and c.history_ok and c.openai_ok and c.answer_ok
    )
    print()
    print("=" * 72)
    print(f"RELIABILITY SUMMARY: {passed}/{total} messages passed (100% required)")
    print("=" * 72)
    for check in message_checks:
        status = "PASS" if not check.error else "FAIL"
        print(
            f"{status} | {check.phase} | test #{check.test_id} turn {check.turn} | "
            f"sqlite={check.sqlite_ok} history={check.history_ok} "
            f"openai={check.openai_ok} answer={check.answer_ok}"
        )
        if check.error:
            print(f"       -> {check.error}")
    print("=" * 72)


async def main() -> None:
    openai_service.client.responses.create = capturing_create  # type: ignore[method-assign]

    init_db()
    print(f"Database: {DATABASE_PATH}")
    print(f"Running {len(CASES)} conversation tests (2 turns each)...")

    for case in CASES:
        await run_conversation("before_restart", case)
        print(f"  PASS before_restart test #{case.test_id} ({case.name})")

    print("\nSimulating bot restart (init_db + settings reload, DB kept)...")
    simulate_bot_restart()

    for case in CASES:
        offset_case = ConversationCase(
            test_id=case.test_id,
            telegram_id=case.telegram_id + 200000,
            name=case.name,
            intro=case.intro,
            recall_question=case.recall_question,
        )
        await run_conversation("after_restart", offset_case)
        print(f"  PASS after_restart test #{case.test_id} ({case.name})")

    print_summary()

    failed = [c for c in message_checks if c.error]
    if failed:
        first = failed[0]
        raise SystemExit(
            f"\nRELIABILITY TEST FAILED: {len(failed)} message(s) failed. "
            f"First failure: {first.phase} test #{first.test_id} turn {first.turn}: "
            f"{first.error}"
        )

    print("\nALL RELIABILITY TESTS PASSED (100% success rate)")
    print(f"Total messages verified: {len(message_checks)}")


if __name__ == "__main__":
    asyncio.run(main())
