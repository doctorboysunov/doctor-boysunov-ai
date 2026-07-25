"""Classify uploaded patient files for medical history linking."""

from __future__ import annotations

import re

from app.domain.patient_file_types import FILE_CATEGORIES
from app.domain.medical_history_types import MEDICAL_RECORD_TYPES


def detect_file_category(file_name: str, mime_type: str | None) -> str:
    lower_name = file_name.lower()
    mime = (mime_type or "").lower()

    if mime.startswith("image/") or lower_name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "image"
    if mime == "application/pdf" or lower_name.endswith(".pdf"):
        return "pdf"
    if lower_name.endswith((".doc", ".docx")) or "word" in mime:
        return "word"
    return "document"


def detect_record_type(
    file_name: str,
    mime_type: str | None,
    caption: str | None,
    file_category: str,
) -> str:
    text = f"{file_name} {caption or ''}".lower()

    if re.search(r"\b(mri|mrt|magnet.?rezonans)\b", text):
        return "mri"
    if re.search(r"\b(ct|kt|kompyuter tomograf)\b", text):
        return "ct"
    if re.search(r"\b(emg|elektromiograf)\b", text):
        return "emg"
    if re.search(r"\b(laborator\w*|lab\b|qon tahlil|analiz|biokimyo)\b", text):
        return "laboratory"

    if file_category == "image":
        return "consultation"
    if file_category == "pdf" and "hisobot" in text:
        return "consultation"
    return "consultation"


def build_history_content(file_name: str, record_type: str, caption: str | None) -> str:
    label = record_type.upper()
    if caption:
        return f"{label} file uploaded: {file_name} — {caption.strip()}"
    return f"{label} file uploaded: {file_name}"


def validate_file_category(file_category: str) -> None:
    if file_category not in FILE_CATEGORIES:
        raise ValueError(f"Invalid file_category: {file_category!r}")


def validate_record_type(record_type: str) -> None:
    if record_type not in MEDICAL_RECORD_TYPES:
        raise ValueError(f"Invalid record_type: {record_type!r}")
