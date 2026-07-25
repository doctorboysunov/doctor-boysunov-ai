"""Extract patient fields from image OCR via OpenAI vision."""

from __future__ import annotations

import base64
import json

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.services.patient_intake.extraction import ExtractedPatient, clean_name
from app.services.patient_intake.phone import normalize_phone

client = OpenAI(api_key=OPENAI_API_KEY)


def extract_patient_from_image(image_bytes: bytes, *, mime_type: str = "image/jpeg") -> ExtractedPatient | None:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Read this image and extract patient full_name and phone_number. "
                            "Return strict JSON: {\"full_name\": \"...\", \"phone_number\": \"...\"}."
                        ),
                    },
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
        text={"format": {"type": "json_object"}},
    )
    payload = json.loads(response.output_text)
    full_name = payload.get("full_name")
    phone_number = payload.get("phone_number")
    if not full_name or not phone_number:
        return None

    return ExtractedPatient(
        full_name=clean_name(str(full_name)),
        phone_number=normalize_phone(str(phone_number)),
    )
