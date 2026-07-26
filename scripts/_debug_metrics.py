"""Find cases dragging down metric averages."""
import sys
sys.path.insert(0, ".")
from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.evaluator import evaluate_structural

cases = CHALLENGE_CASES_100
metrics = [
    "differential_diagnosis_quality",
    "red_flag_detection",
    "specialty_routing",
]

for metric in metrics:
    low = []
    for c in cases:
        r = evaluate_structural(c)
        v = getattr(r.scores, metric)
        if v < 98:
            low.append((v, c.id, c.title, r.routing_primary, r.routing_secondary, r.missed_red_flags))
    low.sort()
    print(f"\n=== {metric} ({len(low)} below 98) ===")
    for row in low[:25]:
        title = row[2].encode("ascii", "replace").decode()
        print(f"  {row[0]:5.1f} {row[1]} {title} primary={row[3]} sec={row[4]} missed={row[5]}")
