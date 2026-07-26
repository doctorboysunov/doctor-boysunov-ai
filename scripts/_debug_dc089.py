import sys
sys.path.insert(0, ".")
from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.evaluator import evaluate_structural
from app.medical_brain.router import route_medical_specialties

for cid in ("dc_089", "dc_020", "dc_069"):
    c = next(x for x in CHALLENGE_CASES_100 if x.id == cid)
    text = c.full_patient_text
    r = route_medical_specialties(text)
    e = evaluate_structural(c)
    print(cid, "route", r.primary, r.secondary)
    print("  scores", e.scores.to_dict())
    print("  text", text[:80])

low = []
for c in CHALLENGE_CASES_100:
    e = evaluate_structural(c)
    if e.scores.differential_diagnosis_quality < 98:
        low.append((e.scores.differential_diagnosis_quality, c.id, e.routing_primary))
print("\nDD below 98:", len(low))
for row in sorted(low)[:15]:
    print(row)
