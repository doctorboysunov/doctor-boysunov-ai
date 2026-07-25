"""Store patient files on disk, organized per user."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import PATIENT_FILES_PATH


def get_patient_directory(user_id: int) -> Path:
    directory = Path(PATIENT_FILES_PATH) / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_filename(file_name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", file_name.strip())
    return cleaned or "upload.bin"


def store_patient_file(user_id: int, file_name: str, file_bytes: bytes) -> Path:
    directory = get_patient_directory(user_id)
    destination = directory / _safe_filename(file_name)
    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while destination.exists():
            destination = directory / f"{stem}_{counter}{suffix}"
            counter += 1
    destination.write_bytes(file_bytes)
    return destination
