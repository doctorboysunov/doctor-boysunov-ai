"""Voice message transcription."""

from __future__ import annotations

import io
import logging

from openai import OpenAI

from app.config import OPENAI_API_KEY

logger = logging.getLogger("doctor_boysunov.transcribe")

client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe_audio(audio_bytes: bytes, *, filename: str = "voice.ogg") -> str:
    if not audio_bytes:
        raise ValueError("Audio payload is empty")

    logger.info("transcribe_start bytes=%s filename=%s", len(audio_bytes), filename)
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename
    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=buffer,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("transcribe_api_failed error=%s", exc)
        raise

    transcript = result.text.strip()
    logger.info("transcribe_ok transcript=%r", transcript)
    if not transcript:
        raise ValueError("Speech recognition returned empty text")
    return transcript
