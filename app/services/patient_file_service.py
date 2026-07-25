"""Link uploaded files to permanent medical history."""

from __future__ import annotations

from typing import Any

from app.repositories.medical_history_repository import add_medical_record
from app.repositories.patient_file_repository import add_patient_file
from app.services.file_classification import (
    build_history_content,
    detect_file_category,
    detect_record_type,
)
from app.services.patient_file_storage import store_patient_file


def link_patient_file_to_history(
    user_id: int,
    *,
    file_name: str,
    file_bytes: bytes,
    mime_type: str | None = None,
    caption: str | None = None,
    telegram_file_id: str | None = None,
) -> dict[str, Any]:
    file_category = detect_file_category(file_name, mime_type)
    record_type = detect_record_type(file_name, mime_type, caption, file_category)
    stored_path = store_patient_file(user_id, file_name, file_bytes)
    content = build_history_content(file_name, record_type, caption)

    history = add_medical_record(
        user_id,
        record_type,
        content,
        notes=f"stored_path={stored_path}",
    )

    patient_file = add_patient_file(
        user_id,
        history["id"],
        file_name=file_name,
        stored_path=str(stored_path),
        file_category=file_category,
        mime_type=mime_type,
        telegram_file_id=telegram_file_id,
        caption=caption,
    )

    return {
        "medical_history": history,
        "patient_file": patient_file,
        "record_type": record_type,
        "file_category": file_category,
    }
