# Medical OS V1 — Production Foundation

**Version:** 1.0.0  
**Status:** Active development  
**Scope:** Production-ready clinical core only

---

## V1 Mission

Build the **clinical operating system foundation** — not a demo chatbot.

Every module ships with automated tests, evaluation gates, and quality reports before the next milestone begins.

---

## V1 Scope (IN)

| # | Module | V1 Deliverable |
|---|--------|----------------|
| 1 | Platform Architecture | Frozen contracts, unified API, quality gate |
| 2 | Medical Brain | Stable 7-step pipeline, specialty router, eval suite |
| 3 | EMR | Structured AI assessment, doctor review workflow |
| 4 | Doctor Dashboard | Web UI — review queue, patient EMR, sign-off |
| 5 | Platform API | Single FastAPI entry point, stable `/api/v1/*` |

## V1 Scope (OUT — later phases)

Marketing AI, social media, advanced automation, billing, video, CRM, native mobile apps, multi-tenant.

---

## Milestone Quality Gate

After **every** milestone:

```
python scripts/run_medical_os_quality_gate.py --milestone N
```

Gate runs:
1. Automated unit/integration tests for the milestone
2. Medical Brain evaluation (20 multi-specialty scenarios)
3. Clinical Brain evaluation (100 neurology scenarios)
4. Generates `data/medical_os_quality_report.md`
5. Lists weaknesses — must be addressed or documented before next milestone

**Deploy rule:** Quality gate must pass 100% before any production deploy.

---

## Module Boundaries

```
Telegram (channel adapter)
       ↓
Platform API (/api/v1)
       ↓
Consultation Engine → Medical Brain → EMR Service
       ↓                                    ↓
Doctor Dashboard (web) ←────────── Review Queue
```

Clinical reasoning never flows through dashboard UI logic. Dashboard reads/writes EMR via API only.

---

## Frozen Contracts (V1)

| Contract | Location | Version |
|----------|----------|---------|
| Medical Brain pipeline schema | `app/medical_brain/contract.py` | 1.0 |
| EMR AI assessment schema | `app/domain/emr.py` | 1.0 |
| Platform API routes | `app/api/platform_api.py` | 1.0 |

Changes to frozen contracts require eval re-run and version bump.

---

## API Entry Point

```bash
uvicorn app.api.platform_api:app --host 0.0.0.0 --port 8000
```

Dashboard: `http://localhost:8000/dashboard/`

---

## Current Milestone Tracker

| Milestone | Status |
|-----------|--------|
| M1 Platform Architecture | ✅ |
| M2 Medical Brain | ✅ |
| M3 EMR V1 | ✅ |
| M4 Doctor Dashboard | ✅ |
| M5 Platform API | ✅ |
