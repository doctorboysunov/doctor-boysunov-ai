import sys
sys.path.insert(0, ".")
from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.evaluator import evaluate_structural

for cid in ("dc_045", "dc_063"):
    c = next(x for x in CHALLENGE_CASES_100 if x.id == cid)
    e = evaluate_structural(c)
    print(cid, e.routing_primary, e.routing_secondary)
    print(" ", e.scores.to_dict(), e.failure_reasons)
    print(" ", c.full_patient_text)
