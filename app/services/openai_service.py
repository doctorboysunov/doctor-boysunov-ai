import json
import logging
from typing import Any

from openai import OpenAI

from app.config import OPENAI_MODEL
from app.settings import get_settings
from app.domain.conversation_mode import ConversationMode
from app.infrastructure.ai.prompt_builder import build_medical_system_prompt
from app.safety.safety_layer import (
    enforce_safety,
    extract_latest_user_message,
)
from app.repositories.conversation_repository import (
    get_last_response_id,
    set_last_response_id,
)
from app.services.patient_context import build_profile_instructions

client = OpenAI(api_key=get_settings().openai_api_key)
logger = logging.getLogger("doctor_boysunov.openai")


def _openai_client() -> OpenAI:
    global client
    current_key = get_settings().openai_api_key
    if client.api_key != current_key:
        client = OpenAI(api_key=current_key)
    return client

Message = dict[str, str]


def _build_input(messages: list[Message]) -> list[dict[str, Any]]:
    if not messages:
        raise ValueError("messages must not be empty")
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
    context_instructions: str | None = None,
    conversation_id: int | None = None,
) -> str:
    if isinstance(messages, str):
        history = [{"role": "user", "content": messages}]
    else:
        history = messages

    if not history:
        raise ValueError("messages must not be empty")

    previous_response_id = (
        get_last_response_id(conversation_id) if conversation_id is not None else None
    )

    if previous_response_id and len(history) >= 2:
        api_input: str | list[dict[str, Any]] = history[-1]["content"]
    elif len(history) == 1:
        api_input = history[0]["content"]
    else:
        api_input = _build_input(history)

    profile_instructions = context_instructions or build_profile_instructions(patient_profile)
    instructions = build_medical_system_prompt(
        profile_instructions=profile_instructions,
        conversation_mode=conversation_mode,
    )

    request_kwargs: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "input": api_input,
        "instructions": instructions,
    }
    if previous_response_id and len(history) >= 2:
        request_kwargs["previous_response_id"] = previous_response_id

    user_message = extract_latest_user_message(history)

    print("=== BEFORE OPENAI ===")
    print(f"safety_instructions={json.dumps(build_medical_system_prompt(conversation_mode=conversation_mode).split(chr(10))[0][:80], ensure_ascii=False)}")
    if profile_instructions:
        print(f"patient_profile_context={json.dumps(profile_instructions, ensure_ascii=False)}")
    else:
        print("patient_profile_context=null")

    print("=== OPENAI REQUEST ===")
    print(f"model={OPENAI_MODEL}")
    print(f"input={json.dumps(api_input, ensure_ascii=False, indent=2)}")

    response = _openai_client().responses.create(**request_kwargs)
    raw_output = response.output_text

    if conversation_id is not None and getattr(response, "id", None):
        set_last_response_id(conversation_id, response.id)

    print(f"openai_output={raw_output!r}")

    safe_output, safety_meta = enforce_safety(
        user_message=user_message,
        ai_response=raw_output,
    )

    print("=== SAFETY LAYER ===")
    print(f"safety_meta={json.dumps(safety_meta, ensure_ascii=False)}")
    print(f"safe_output={safe_output!r}")

    return safe_output
