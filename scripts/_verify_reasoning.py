"""Quick sanity check for physician reasoning module."""
import sys
sys.path.insert(0, ".")
from app.medical_brain.reasoning import (
    build_reasoning_context,
    detect_contradictions,
    format_reasoning_block,
)

turns = [
    "1 haftadan beri isitmam bor deb o'ylayman",
    "Aslida 3 kun — 39.5, titroq, nafas qisish bor.",
]
msgs = [{"role": "user", "content": t} for t in turns]
ctx = build_reasoning_context(
    known_facts={"profile": "Male, 55y"},
    session_messages=msgs,
    topics_covered=["opening_complaint"],
    detected_flags=["fever"],
    is_emergency=True,
    primary_specialty="internal_medicine",
    secondary_specialties=["emergency_medicine"],
)
assert detect_contradictions(turns), "should detect duration contradiction"
block = format_reasoning_block(ctx)
assert "Contradictions" in block
assert "Whole story" in block
print("reasoning module OK")
