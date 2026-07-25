"""Step 3.5: link uploaded files to patient medical history."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "data" / "test_step_3_5.db"
TEST_FILES = ROOT / "data" / "test_step_3_5_files"

if TEST_DB.exists():
    TEST_DB.unlink()
if TEST_FILES.exists():
    import shutil

    shutil.rmtree(TEST_FILES)

os.environ["DATABASE_PATH"] = str(TEST_DB)
os.environ["PATIENT_FILES_PATH"] = str(TEST_FILES)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "verify-token")
os.environ.setdefault("OPENAI_API_KEY", "verify-key")

sys.path.insert(0, str(ROOT))

from importlib import reload

import app.config as config_module
import app.settings as settings_module

reload(settings_module)
reload(config_module)

from app.db.connection import get_connection, init_db  # noqa: E402
from app.handlers.documents import handle_patient_file  # noqa: E402
from app.repositories.conversation_repository import upsert_user  # noqa: E402
from app.repositories.medical_history_repository import get_medical_history  # noqa: E402
from app.repositories.patient_file_repository import (  # noqa: E402
    get_patient_file_for_history,
    get_patient_files,
)
from app.services.file_classification import (  # noqa: E402
    detect_file_category,
    detect_record_type,
)
from app.services.patient_file_service import link_patient_file_to_history  # noqa: E402
from app.settings import get_settings  # noqa: E402


def assert_classification(
    file_name: str,
    mime_type: str | None,
    caption: str | None,
    expected_category: str,
    expected_record_type: str,
) -> None:
    category = detect_file_category(file_name, mime_type)
    record_type = detect_record_type(file_name, mime_type, caption, category)
    assert category == expected_category, (file_name, category)
    assert record_type == expected_record_type, (file_name, record_type)


async def run_document_handler(
    *,
    telegram_id: int,
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    caption: str | None = None,
) -> None:
    fake_file = MagicMock()
    fake_file.download_as_bytearray = AsyncMock(return_value=bytearray(file_bytes))

    document = MagicMock()
    document.file_name = file_name
    document.mime_type = mime_type
    document.file_id = f"file-{file_name}"
    document.file_unique_id = f"unique-{file_name}"
    document.get_file = AsyncMock(return_value=fake_file)

    user = MagicMock()
    user.id = telegram_id
    user.username = "file_user"
    user.full_name = "File User"

    message = MagicMock()
    message.photo = None
    message.document = document
    message.caption = caption
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.message = message
    update.effective_user = user

    await handle_patient_file(update, None)
    message.reply_text.assert_awaited()


async def main() -> None:
    init_db()

    assert_classification("scan.jpg", "image/jpeg", None, "image", "consultation")
    assert_classification("mri_report.pdf", "application/pdf", "MRI hisobot", "pdf", "mri")
    assert_classification("kt_skan.pdf", "application/pdf", "KT natija", "pdf", "ct")
    assert_classification(
        "lab_result.pdf",
        "application/pdf",
        "Laboratoriya analizi",
        "pdf",
        "laboratory",
    )
    assert_classification(
        "report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        None,
        "word",
        "consultation",
    )

    user_a = upsert_user(telegram_id=990001, username="a", full_name="A")
    user_b = upsert_user(telegram_id=990002, username="b", full_name="B")

    uploads = [
        ("mri_lumbar.pdf", b"PDF-MRI", "application/pdf", "MRI hisobot"),
        ("lab_blood.pdf", b"PDF-LAB", "application/pdf", "Laboratoriya natijasi"),
        ("consultation.docx", b"DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", None),
        ("xray.jpg", b"JPEG", "image/jpeg", "Rentgen surati"),
    ]

    for file_name, payload, mime_type, caption in uploads:
        result = link_patient_file_to_history(
            user_a,
            file_name=file_name,
            file_bytes=payload,
            mime_type=mime_type,
            caption=caption,
            telegram_file_id=f"tg-{file_name}",
        )
        history = result["medical_history"]
        patient_file = result["patient_file"]
        assert patient_file["medical_history_id"] == history["id"]
        assert Path(patient_file["stored_path"]).exists()
        assert str(user_a) in patient_file["stored_path"]

    history = get_medical_history(user_a)
    assert len(history) == 4
    files = get_patient_files(user_a)
    assert len(files) == 4
    assert all(get_patient_file_for_history(row["id"]) is not None for row in history)

    link_patient_file_to_history(
        user_b,
        file_name="patient_b.pdf",
        file_bytes=b"B-PDF",
        mime_type="application/pdf",
        caption="KT hisobot",
    )
    assert len(get_patient_files(user_a)) == 4
    assert len(get_patient_files(user_b)) == 1
    assert len(list((TEST_FILES / str(user_a)).glob("*"))) == 4
    assert len(list((TEST_FILES / str(user_b)).glob("*"))) == 1

    await run_document_handler(
        telegram_id=990001,
        file_name="telegram_mri.pdf",
        file_bytes=b"TG-PDF",
        mime_type="application/pdf",
        caption="MRT hisobot",
    )

    files_after_handler = get_patient_files(user_a)
    assert len(files_after_handler) == 5
    assert files_after_handler[-1]["file_name"] == "telegram_mri.pdf"
    assert get_medical_history(user_a)[-1]["record_type"] == "mri"

    with get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "patient_files" in tables

    get_settings.cache_clear()
    init_db()

    reloaded_files = get_patient_files(user_a)
    assert len(reloaded_files) == 5
    assert Path(reloaded_files[0]["stored_path"]).exists()

    print("Step 3.5 OK: patient files organized per user and linked to medical history")


if __name__ == "__main__":
    asyncio.run(main())
