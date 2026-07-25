"""Live OpenAI test: does Responses API honor manual message history?"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)


def test_manual_history() -> None:
    print("=== TEST A: manual history array ===")
    input_messages = [
        {"role": "user", "content": "Mening ismim Sohibnazar.", "type": "message"},
        {
            "role": "assistant",
            "content": "Tanishganimdan xursandman, Sohibnazar!",
            "type": "message",
            "phase": "final_answer",
        },
        {"role": "user", "content": "Mening ismim kim?", "type": "message"},
    ]
    print("input:", json.dumps(input_messages, ensure_ascii=False, indent=2))
    response = client.responses.create(model=OPENAI_MODEL, input=input_messages)
    print("output:", response.output_text)


def test_previous_response_id() -> None:
    print("\n=== TEST B: previous_response_id chain ===")
    first = client.responses.create(
        model=OPENAI_MODEL,
        input="Mening ismim Sohibnazar.",
    )
    print("turn1:", first.output_text)
    print("response_id:", first.id)

    second = client.responses.create(
        model=OPENAI_MODEL,
        previous_response_id=first.id,
        input="Mening ismim kim? Javobni o'zbek tilida bering.",
    )
    print("turn2:", second.output_text)


def test_chat_completions() -> None:
    print("\n=== TEST C: chat.completions message history ===")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Mening ismim Sohibnazar."},
            {"role": "assistant", "content": "Tanishganimdan xursandman, Sohibnazar!"},
            {"role": "user", "content": "Mening ismim kim? Javobni o'zbek tilida bering."},
        ],
    )
    print("output:", response.choices[0].message.content)


if __name__ == "__main__":
    test_manual_history()
    test_previous_response_id()
    try:
        test_chat_completions()
    except Exception as exc:
        print("chat completions test skipped/failed:", exc)
