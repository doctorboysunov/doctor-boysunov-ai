"""Voice message transcription."""

from __future__ import annotations

import io

from openai import OpenAI

from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe_audio(audio_bytes: bytes, *, filename: str = "voice.ogg") -> str:
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer,
    )
    return result.text.strip()
