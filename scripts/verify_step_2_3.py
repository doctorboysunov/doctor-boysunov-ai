import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.services.openai_service import _build_input, ask_ai


assert _build_input("Salom") == "Salom"

history = [
    {"role": "user", "content": "Salom"},
    {"role": "assistant", "content": "Assalomu alaykum!"},
    {"role": "user", "content": "Qanday yordam bera olasiz?"},
]
built = _build_input(history)
assert built[0] == {"role": "user", "content": "Salom", "type": "message"}
assert built[1]["phase"] == "final_answer"
assert built[2]["type"] == "message"

try:
    _build_input([])
    raise AssertionError("expected ValueError for empty history")
except ValueError as exc:
    assert str(exc) == "messages must not be empty"

try:
    _build_input([{"role": "system", "content": "test"}])
    raise AssertionError("expected ValueError for system role")
except ValueError as exc:
    assert "Invalid message role" in str(exc)

# chat.py still uses single-string calls; signature remains compatible.
assert ask_ai.__annotations__["messages"] == str | list[dict[str, str]]

print("Step 2.3 OK: single-string and multi-turn input building verified")
