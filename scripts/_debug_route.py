import sys, re
sys.path.insert(0, ".")
from app.medical_brain.router import route_medical_specialties, _resolve_primary_with_overrides, _score_specialties

samples = {
    "pemphigus": "Og'izda pufakchalar, terida ham pufak Ha, juda og'riqli",
    "renal": "Belda o'tkir og'riq, qusish Siydikda qon bor",
    "torsion": "Qorin pastida o'tkir og'riq, ko'ngil aynish Yo'q. Og'riq birdan boshlandi, qusdim",
}
for k, v in samples.items():
    n = v.strip().lower()
    m = re.search(r"pufakchalar|pufak.*og['']?iz|pemphigus|butun tana.*pufak", n)
    scores = _score_specialties(v)
    sorted_scores = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    primary = _resolve_primary_with_overrides(v, sorted_scores)
    r = route_medical_specialties(v)
    print(k, "regex", bool(m), "override", primary, "route", r.primary, r.secondary, "scores", dict(sorted(scores.items(), key=lambda x: -x[1])[:3]))
