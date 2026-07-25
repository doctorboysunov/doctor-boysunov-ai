import json
import logging
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL

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


def ask_ai(messages: str | list[Message]) -> str:
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

    print("=== OPENAI REQUEST ===")
    print(f"model={OPENAI_MODEL}")
    print(f"input={json.dumps(api_input, ensure_ascii=False, indent=2)}")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=api_input,
    )

    print(f"openai_output={response.output_text!r}")

    return response.output_text
