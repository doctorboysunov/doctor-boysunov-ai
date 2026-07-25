import json
import logging
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.domain.conversation_mode import ConversationMode
from app.safety.instructions import build_safety_instructions
from app.safety.safety_layer import (
    combine_instructions,
    enforce_safety,
    extract_latest_user_message,
)
from app.services.patient_context import build_profile_instructions
from app.services.receptionist_instructions import build_receptionist_instructions

client = OpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger("doctor_boysunov.openai")

Message = dict[str, str]


def _build_input(messages: list[Message]) -> list[dict[str, Any]]:
    api_messages: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")

        if role not in {"user", "assistant"}:
            raise ValueError(f"Invalid message role: {role}")
        if not content:
            raise ValueError("Message content must not be empty")

        api_message: dict[str, Any] = {
            "role": role,
            "content": content,
            "type": "message",
        }
        if role == "assistant":
            api_message["phase"] = "final_answer"

        api_messages.append(api_message)

    return api_messages


def ask_ai(
    messages: str | list[Message],
    patient_profile: dict[str, Any] | None = None,
    *,
    conversation_mode: ConversationMode = "patient",
) -> str:
    if isinstance(messages, str):
        history = [{"role": "user", "content": messages}]
    else:
        history = messages

    if not history:
        raise ValueError("messages must not be empty")

    if len(history) == 1:
        api_input: str | list[dict[str, Any]] = history[0]["content"]
    else:
        api_input = _build_input(history)

    profile_instructions = build_profile_instructions(patient_profile)
    receptionist_instructions = (
        build_receptionist_instructions() if conversation_mode == "patient" else None
    )
    instructions = combine_instructions(
        profile_instructions=profile_instructions,
        receptionist_instructions=receptionist_instructions,
    )

    request_kwargs: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "input": api_input,
        "instructions": instructions,
    }

    user_message = extract_latest_user_message(history)

    print("=== BEFORE OPENAI ===")
    print(f"safety_instructions={json.dumps(build_safety_instructions(), ensure_ascii=False)}")
    if profile_instructions:
        print(f"patient_profile_context={json.dumps(profile_instructions, ensure_ascii=False)}")
    else:
        print("patient_profile_context=null")

    print("=== OPENAI REQUEST ===")
    print(f"model={OPENAI_MODEL}")
    print(f"input={json.dumps(api_input, ensure_ascii=False, indent=2)}")

    response = client.responses.create(**request_kwargs)
    raw_output = response.output_text

    print(f"openai_output={raw_output!r}")

    safe_output, safety_meta = enforce_safety(
        user_message=user_message,
        ai_response=raw_output,
    )

    print("=== SAFETY LAYER ===")
    print(f"safety_meta={json.dumps(safety_meta, ensure_ascii=False)}")
    print(f"safe_output={safe_output!r}")

    return safe_output
