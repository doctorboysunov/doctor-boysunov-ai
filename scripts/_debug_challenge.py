import sys
sys.path.insert(0, ".")
from app.medical_brain.evaluation.clinical_challenge.case_bank import CHALLENGE_CASES_100
from app.medical_brain.evaluation.clinical_challenge.evaluator import evaluate_structural
from app.medical_brain.router import route_medical_specialties

for cid in ["dc_038","dc_047","dc_052","dc_062","dc_063"]:
    c = next(x for x in CHALLENGE_CASES_100 if x.id == cid)
    r = route_medical_specialties(c.full_patient_text)
    ev = evaluate_structural(c)
    print(cid, ev.scores.overall, r.primary, r.secondary, ev.scores.specialty_routing)
