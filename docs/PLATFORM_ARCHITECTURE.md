# Universal Medical AI Platform — System Architecture Blueprint

**Version:** 1.0  
**Horizon:** 5 years (2026–2031)  
**Status:** Design document — no implementation  
**Purpose:** Blueprint for a production-grade, multi-specialty medical AI platform supporting every clinical domain

---

## 1. Executive Vision

This platform is not a chatbot. It is a **clinical operating system** where:

- One **Medical Brain** powers every patient touchpoint
- Every specialty is a **pluggable module**, not a separate product
- Clinical reasoning is **centralized, auditable, and continuously evaluated**
- Business operations (CRM, billing, appointments, marketing) orbit the clinical core without polluting it

**North star:** A patient anywhere (Telegram, WhatsApp, mobile app, web) talks to the same physician-grade AI. A doctor anywhere (dashboard, video, clinic) sees the same structured EMR. An admin anywhere (panel, CRM, analytics) runs the same organization.

---

## 2. Architecture Principles

| Principle | Meaning |
|-----------|---------|
| **Brain-first** | All clinical intelligence flows through Medical Brain. Channels are thin adapters. |
| **Reason, don't script** | Specialty modules inform GPT; they never replace clinical reasoning. |
| **Modular specialties** | Adding a specialty = adding a module. Never changing the core engine. |
| **Separation of concerns** | Clinical / operational / commercial layers are isolated. |
| **Event-driven** | Modules communicate via events and APIs, not direct database coupling. |
| **Evaluation-gated** | No clinical deploy without passing the evaluation suite. |
| **Patient safety** | Emergency detection, disclaimers, and human escalation are non-negotiable. |
| **Multi-tenant ready** | One platform, many clinics, many doctors, many regions. |

---

## 3. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHANNEL LAYER (Adapters)                          │
│  Telegram │ WhatsApp │ iOS App │ Android App │ Web │ Voice │ SMS          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ Platform API (REST + WebSocket)
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                 │
│  Conversation Manager │ Intent Router │ Session Manager │ Channel Router   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         CLINICAL CORE (Heart)                               │
│  ┌─────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐  │
│  │ Medical     │→ │ Clinical Reasoning   │→ │ Safety & Red Flag       │  │
│  │ Brain       │  │ Engine               │  │ Layer                   │  │
│  └──────┬──────┘  └──────────────────────┘  └─────────────────────────┘  │
│         │                                                                   │
│  ┌──────▼──────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Specialty   │  │ Memory       │  │ Evaluation   │  │ Knowledge     │  │
│  │ Registry    │  │ System       │  │ Suite        │  │ Base          │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ Clinical Events
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         CLINICAL DATA LAYER                                 │
│  EMR │ Patient Profile │ Visit Timeline │ Consultation Sessions │ Documents  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         OPERATIONS LAYER                                    │
│  Appointments │ Follow-up Engine │ Video Consult │ Care Manager │ CRM       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         COMMERCIAL LAYER                                    │
│  Billing │ Pricing │ Subscriptions │ AI Marketing │ Analytics │ Reporting   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         ADMIN & GOVERNANCE                                  │
│  Admin Panel │ Doctor Dashboard │ Audit Logs │ RBAC │ Compliance │ Eval Gate│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Specifications

### 4.1 Medical Brain

**Role:** The single entry point for all clinical AI reasoning across every channel and specialty.

**Responsibilities:**
- Receive normalized patient input (text, voice transcript, structured intake)
- Invoke specialty routing (primary + secondary specialties)
- Orchestrate the Clinical Reasoning Engine pipeline
- Produce patient-facing reply (2–4 sentences, natural Uzbek/Russian/English)
- Produce doctor-facing EMR update (never shown to patient)
- Emit clinical events for downstream systems

**Inputs:**
- Patient message + session context
- Patient memory (longitudinal)
- Active specialties
- Red flag signals from Safety Layer

**Outputs:**
- `PatientReply` — safe, natural, one question max
- `MedicalBrainInternal` — full reasoning chain (never patient-visible)
- `DoctorEmrUpdate` — structured clinical artifact
- `ClinicalEvent` — specialty, urgency, confidence, topics covered

**Current state (2026):** Implemented as `medical_brain/` with router, engine, 19 specialty definitions. Delegates neurology depth to Clinical Brain sub-module.

**5-year evolution:**
- Year 1: Universal router + modular specialties (19 → 50+)
- Year 2: Multi-language reasoning, pediatric/geriatric mode switches
- Year 3: Doctor-in-the-loop co-reasoning (AI drafts, doctor approves)
- Year 4: Federated learning from anonymized consult patterns (privacy-preserving)
- Year 5: Real-time multimodal (image, lab PDF, ECG snippet) as reasoning inputs

**Non-goals:** Medical Brain never handles billing, scheduling, or marketing copy directly.

---

### 4.2 Clinical Reasoning Engine

**Role:** The deterministic **pipeline** that structures GPT reasoning into auditable clinical steps.

**7-Step Pipeline (fixed for all specialties):**

| Step | Name | Purpose |
|------|------|---------|
| 0 | Specialty coordination | Confirm primary + secondary; note interactions |
| 1 | Patient meaning | What is the patient actually saying/concerned about? |
| 2 | Memory integration | Merge longitudinal history; never re-ask known facts |
| 3 | Differential hypotheses | Rank 2–4 diagnoses with probability + rationale |
| 4 | Red flags / emergency | Triage assessment per active specialty |
| 5 | Missing information | What high-yield data would change the differential? |
| 6 | Next question selection | ONE highest-value question; reject alternatives explicitly |
| 7 | Patient reply generation | Natural, empathetic, short; max one question |

**Design rules:**
- Pipeline schema is **stable** — specialties plug in at Step 0 and inform Steps 3–6
- GPT fills the pipeline; code validates and enforces structure
- `step6_alternatives_rejected` is mandatory — forces explicit reasoning
- Confidence gates summary: low → keep asking; high + adequate data → summarize

**Relationship to Medical Brain:**
- Medical Brain = orchestrator + I/O + safety
- Clinical Reasoning Engine = the pipeline contract inside Medical Brain

**Evaluation:** Every pipeline change runs against 100+ scenario rubric before deploy.

---

### 4.3 Specialty Modules

**Role:** Pluggable clinical knowledge units. One module per specialty. Unlimited count.

**Module contract (every specialty must implement):**

```
SpecialtyModule {
  id: string                    // e.g. "cardiology"
  label: string                 // Display name
  patterns: string[]            // Routing regex/keywords
  priority: int                 // Tie-break for routing

  // Clinical reference (inform GPT — NOT scripts)
  knowledge: string             // Core domain knowledge
  guidelines: string            // Clinical guidelines summary
  red_flags: string[]           // Must-screen conditions
  expert_priorities: string[]   // High-yield history elements
  avoid_early: string[]         // Low-yield early questions to skip

  // Clinical operations (internal only)
  referral_rules: string[]       // When to refer / escalate
  investigation_suggestions: string[]  // Labs, imaging (internal)
  differential_framework: string // How to think about DDx in this domain

  // Optional depth modules
  sub_modules?: SubModule[]     // e.g. neurology → headache, stroke, vertigo
  presentation_overrides?: Override[]  // Keyword-triggered triage overrides
}
```

**Multi-specialty coordination:**
- Router returns `primary + secondary[]`
- Medical Brain injects **combined reference block**
- GPT asks ONE question serving the combined differential
- Examples: Diabetes+neuropathy, chest pain+arm numbness, rash+fever

**Extensibility model:**
- New specialty = new module file in registry
- **Zero changes** to engine, pipeline, or channels
- Sub-specialties nest under parent (e.g. `neurology/headache`, `neurology/stroke`)
- Third-party specialty packs possible (plugin marketplace, Year 3+)

**Specialty tiers (5-year rollout):**

| Tier | Year | Count | Examples |
|------|------|-------|----------|
| Core | 1 | 19–30 | Current set + nephrology, hematology, geriatrics |
| Extended | 2 | 50+ | All major organ systems + subspecialties |
| Regional | 3 | 70+ | Tropical medicine, local disease patterns |
| Full | 4–5 | 100+ | Every board-certified specialty + allied health |

---

### 4.4 Memory System

**Role:** Longitudinal patient context so the AI never treats each message as the first encounter.

**Memory layers:**

| Layer | Scope | Contents | Retention |
|-------|-------|----------|-----------|
| **Session memory** | Single consultation | Messages, known_facts, topics_covered, specialties | Session duration |
| **Visit memory** | Single visit/encounter | Chief complaint, AI reasoning, EMR draft, urgency | Permanent (EMR) |
| **Patient memory** | Cross-visit | Prior complaints, diagnoses, medications, allergies, visits | Permanent |
| **Population memory** | Anonymized aggregate | Seasonal patterns, common presentations (Year 3+) | Anonymized |

**Memory operations:**
- **Retrieve:** Before each Medical Brain turn — prior complaints, last visit summary, active treatments
- **Write:** After each turn — update known_facts, topics_covered, EMR draft
- **Never re-ask:** If fact exists in memory, GPT must acknowledge and move forward
- **Consent-gated:** Patient controls what persists; GDPR/local compliance

**Storage design:**
- Hot: Redis/session store for active consultations
- Warm: PostgreSQL for patient profile + visit history
- Cold: Object storage for documents, voice recordings, imaging (Year 2+)

**Current state:** Basic session + visit history via `clinical_brain/memory.py` and EMR repositories.

---

### 4.5 EMR (Electronic Medical Record)

**Role:** Structured clinical record generated by AI and enriched by doctors. Single source of clinical truth.

**EMR structure per visit:**

```
Visit {
  patient_id, visit_id, visit_date
  chief_complaint
  history_of_present_illness    // AI-generated narrative
  review_of_systems             // Targeted by active specialties
  past_medical_history          // From patient memory
  medications, allergies
  examination_findings          // Doctor-entered (post-consult)
  ai_preliminary_assessment {
    specialties: []
    differential_diagnoses: []
    red_flags: []
    urgency: routine|urgent|emergency
    confidence: low|medium|high
    internal_reasoning: {}       // Full Medical Brain output — doctor only
  }
  preliminary_diagnosis           // AI suggestion
  final_diagnosis                 // Doctor-confirmed
  icd10_codes[]
  recommended_investigations[]
  treatment_plan
  follow_up_schedule
  doctor_notes
  ai_generated: bool
  doctor_reviewed: bool
  reviewed_at, reviewed_by
}
```

**EMR lifecycle:**
1. AI consultation → `ai_preliminary_assessment` populated
2. Patient selects help menu (online/clinic/continue)
3. Doctor reviews AI draft in Dashboard → edits → confirms
4. Final EMR locked; changes audited

**Access control:**
- Patient: summary only (no internal reasoning, no differentials)
- Doctor: full EMR including AI reasoning chain
- Admin: aggregate only (no individual clinical detail unless authorized)
- AI: read/write draft; never write final diagnosis without doctor

**Current state:** `emr_service`, `emr_api`, visit fields in schema. AI writes via `_persist_doctor_emr`.

---

### 4.6 Doctor Dashboard

**Role:** Clinical command center for physicians. Review AI work, conduct visits, manage patients.

**Core views:**

| View | Purpose |
|------|---------|
| **Today's queue** | Patients awaiting review, urgent flags, video calls |
| **AI consult review** | Pre-visit EMR draft from Medical Brain; approve/edit/reject |
| **Live consult** | Real-time AI-assisted consultation (AI listens, doctor leads) |
| **Patient timeline** | All visits, follow-ups, labs, messages chronologically |
| **Follow-up tracker** | Due/overdue follow-ups with AI-generated check-in scripts |
| **Analytics (clinical)** | Diagnosis patterns, AI accuracy, time saved |

**Doctor actions:**
- Review and sign AI-generated EMR
- Override AI specialty routing
- Escalate to emergency protocol
- Initiate video consult
- Prescribe / order investigations (Phase 3+, with integrations)
- Assign follow-up schedule

**Platforms:** Web (primary), tablet-optimized, mobile companion app (Year 2)

**Current state:** Telegram admin dashboard, `dashboard_api`, morning reports. Web dashboard = Year 1 priority.

---

### 4.7 Patient App

**Role:** Primary patient-facing product beyond messaging bots.

**Core features:**

| Feature | Description |
|---------|-------------|
| **AI consultation** | Same Medical Brain as all channels |
| **Consultation history** | Past summaries (patient-safe, no internal reasoning) |
| **Appointments** | Book, reschedule, cancel, reminders |
| **Video consult** | Join doctor video call in-app |
| **Documents** | Upload labs, imaging, prescriptions (OCR → EMR) |
| **Medications & reminders** | From EMR + follow-up engine |
| **Profile & consents** | Demographics, insurance, data preferences |
| **Help menu** | Continue questions / online consult / clinic visit |

**Design principle:** Patient app is a **channel adapter** — zero clinical logic inside the app. All intelligence via Platform API → Medical Brain.

**Platforms:** iOS + Android (Year 1–2), responsive web (Year 1)

**Current state:** Telegram bot is the de facto patient app. Native apps = Year 1 roadmap.

---

### 4.8 Admin Panel

**Role:** Operations control for clinic owners and platform administrators.

**Modules:**

| Module | Functions |
|--------|-----------|
| **Clinic management** | Locations, specialties offered, doctor roster, hours |
| **User management** | Doctors, staff, roles, permissions (RBAC) |
| **Consultation oversight** | Active sessions, emergency alerts, quality flags |
| **Communication** | Message history, resend, channel config |
| **Appointments admin** | Confirm, cancel, reschedule, waitlist |
| **Follow-up admin** | Treatment plans, due follow-ups, bulk run |
| **Evaluation dashboard** | AI quality scores, regression alerts, deploy gate status |
| **System config** | AI model version, specialty packs enabled, languages |

**Current state:** Telegram admin handlers (appointments, dashboard, follow-ups, communications, clinics). Web admin panel = Year 1.

---

### 4.9 CRM

**Role:** Patient relationship management — acquisition, engagement, retention, lifecycle.

**CRM entities:**

```
Lead → Prospect → Patient → Active → Follow-up → Retained / Churned
```

**Capabilities:**

| Capability | Description |
|------------|-------------|
| **Lead capture** | Web forms, WhatsApp, referral links, marketing campaigns |
| **Patient 360** | Profile + all touchpoints (consults, appointments, payments, messages) |
| **Segmentation** | By specialty, urgency, visit type, geography, engagement |
| **Pipeline** | Consultation → appointment booked → visit completed → follow-up |
| **Tasks & reminders** | Staff tasks for callbacks, no-shows, re-engagement |
| **AI-assisted outreach** | Follow-up Engine + AI Marketing generate personalized messages |

**Integration points:**
- Receives `ClinicalEvent` (consult completed, urgency, specialty)
- Sends triggers to Follow-up Engine and AI Marketing
- Reads EMR summary (not internal reasoning) for context

**Current state:** Patient profiles, conversation history, care manager. Full CRM = Year 1–2.

---

### 4.10 Appointment System

**Role:** Scheduling engine connecting patients, doctors, and clinics.

**Entities:**
```
Clinic → Doctor → Availability → Slot → Appointment → Visit
```

**Features:**
- Online booking (from help menu, app, web)
- Specialty-aware routing (book neurology vs cardiology)
- Urgency-aware prioritization (AI flags urgent → fast-track slot)
- Reminders (SMS, push, Telegram, WhatsApp) via Communication Service
- Waitlist and auto-fill on cancellation
- Video vs in-person vs phone visit types
- Admin confirm/cancel/reschedule (current Telegram admin flow)

**Events emitted:**
- `appointment.booked`, `appointment.confirmed`, `appointment.cancelled`
- `appointment.reminder.sent`, `appointment.no_show`

**Current state:** Appointment repository, admin handlers, notifications. Online patient booking = Year 1.

---

### 4.11 Billing

**Role:** Monetization layer — completely separated from clinical core.

**Models (support multiple simultaneously):**

| Model | Description |
|-------|-------------|
| **Per-consultation** | Pay per AI consult or doctor visit |
| **Subscription** | Monthly unlimited AI + N doctor visits |
| **Insurance** | Integration with local insurers (Year 3+) |
| **Clinic SaaS** | Platform fee per clinic per month |

**Components:**
- Pricing engine (plans, discounts, promo codes)
- Payment gateway abstraction (Stripe, local providers)
- Invoice generation
- Refund/dispute handling
- Revenue reporting → Analytics

**Clinical firewall:** Medical Brain never knows price. Billing never influences clinical reasoning.

**Current state:** Pricing handler (basic). Full billing = Year 2.

---

### 4.12 Video Consultation

**Role:** Real-time doctor-patient video with optional AI assist.

**Architecture:**
```
Patient App ←→ WebRTC/Media Server ←→ Doctor Dashboard
                      │
                      ▼
              AI Assist Layer (optional)
              - Live transcription
              - Real-time differential suggestions (doctor-only sidebar)
              - Auto EMR draft from conversation
```

**Modes:**
1. **AI-only consult** — Medical Brain via text/voice (current)
2. **Doctor-led video** — Doctor conducts; AI pre-populated EMR draft visible
3. **AI-assisted video** — Doctor + AI co-pilot (AI suggests questions doctor can ask)

**Safety:** AI suggestions during live video are **doctor-only**, never auto-sent to patient.

**Provider options:** Twilio, Daily.co, or self-hosted (Janus/mediasoup). Abstract behind `VideoProvider` interface.

**Timeline:** Year 1 (basic video), Year 2 (AI assist), Year 3 (multi-party: doctor + patient + interpreter)

---

### 4.13 Follow-up Engine

**Role:** Automated post-visit patient engagement driven by clinical context.

**Flow:**
```
Visit completed → Follow-up Planner → Schedule created → Processor (cron)
    → AI generates personalized check-in message → Communication Service sends
    → Patient reply → Medical Brain (follow-up mode) → Update EMR
    → Doctor alerted if red flags
```

**Follow-up types:**
- Post-consultation check (24h, 72h, 1 week)
- Treatment adherence (medication reminders)
- Symptom monitoring (structured questions based on diagnosis)
- Chronic disease management (diabetes, hypertension — Year 2+)
- Re-engagement (churned patients)

**Current state:** `follow_up_scheduler`, `follow_up_processor`, `follow_up_planner`, admin follow-up handlers. Mature foundation.

---

### 4.14 AI Marketing

**Role:** AI-generated, personalized, compliant patient outreach for acquisition and retention.

**Capabilities:**
- Campaign generation (seasonal health tips, specialty promotions)
- Personalized messages based on CRM segments + patient history
- A/B testing of message variants
- Compliance guardrails (no diagnosis in marketing, no false claims)
- Multi-channel delivery via Communication Service

**Clinical firewall:** AI Marketing uses EMR **summary** only. Never accesses `MedicalBrainInternal`.

**Timeline:** Year 2 (basic campaigns), Year 3 (automated lifecycle marketing)

---

### 4.15 Analytics

**Role:** Business intelligence and clinical quality measurement.

**Dashboard categories:**

| Category | Metrics |
|----------|---------|
| **Clinical quality** | Eval scores, regression trends, specialty accuracy, emergency detection rate |
| **Operations** | Consultations/day, appointment conversion, no-show rate, response time |
| **Financial** | Revenue, ARPU, subscription churn, payment success |
| **Engagement** | DAU/MAU, channel distribution, follow-up response rate |
| **AI performance** | Model version comparison, confidence distribution, question efficiency |

**Data pipeline:**
```
Events → Event Bus → Stream processor → Data warehouse → Dashboards
```

**Timeline:** Year 1 (operational dashboards), Year 2 (clinical quality), Year 3 (predictive)

---

### 4.16 API Structure

**Role:** Single Platform API consumed by all channels and modules.

**Design:** REST + WebSocket + Event Bus

#### REST API (external-facing)

```
/api/v1/
├── auth/                    # JWT, OAuth, API keys
├── patients/                # Profile, consents, documents
├── consultations/           # Start, continue, history
│   ├── POST /start          # → Medical Brain
│   ├── POST /{id}/message   # → Medical Brain
│   └── GET  /{id}/summary   # Patient-safe summary
├── appointments/            # CRUD, availability
├── emr/                     # Doctor access only
│   ├── GET  /visits/{id}
│   ├── PUT  /visits/{id}/review
│   └── GET  /patients/{id}/timeline
├── follow-ups/              # Schedule, due, respond
├── video/                   # Session create, join token
├── billing/                 # Plans, payments, invoices
├── admin/                   # Clinic, users, config
├── crm/                     # Leads, segments, tasks
└── analytics/               # Reports, exports
```

#### Internal service API (module-to-module)

```
/internal/v1/
├── medical-brain/reason     # Core reasoning (not public)
├── specialty/route          # Specialty classification
├── memory/retrieve          # Patient memory lookup
├── memory/write             # Update patient memory
├── safety/check             # Red flag detection
├── communication/send       # Multi-channel message dispatch
├── evaluation/run           # Trigger eval suite
└── events/publish           # Event bus publish
```

#### WebSocket (real-time)

```
/ws/v1/
├── consultations/{id}       # Live AI consult stream
├── video/{session_id}       # Signaling (or delegate to WebRTC provider)
├── dashboard/doctor         # Live queue updates
└── admin/alerts             # Emergency alerts, system events
```

#### Event Bus (async module communication)

```
Events (pub/sub):
├── clinical.consultation.started
├── clinical.consultation.message
├── clinical.consultation.completed
├── clinical.emergency.detected
├── clinical.emr.draft_created
├── clinical.emr.reviewed
├── ops.appointment.booked
├── ops.appointment.confirmed
├── ops.follow_up.due
├── ops.follow_up.completed
├── comm.message.sent
├── comm.message.received
├── billing.payment.completed
├── marketing.campaign.sent
└── system.eval.regression_detected
```

**Current state:** Partial REST (`emr_api`, `dashboard_api`, `clinic_api`, `patient_intake_api`). Full Platform API = Year 1 foundation.

---

## 5. Module Communication Map

### 5.1 Primary data flows

```
Patient Message
    │
    ▼
Channel Adapter (Telegram/App/Web)
    │  POST /api/v1/consultations/{id}/message
    ▼
Conversation Manager
    │  intent analysis → session routing
    ▼
Medical Brain
    ├──→ Specialty Router → Specialty Modules (reference)
    ├──→ Memory System (read/write)
    ├──→ Safety Layer (red flags)
    ├──→ Clinical Reasoning Engine (7-step pipeline)
    │         └──→ GPT (OpenAI / future models)
    ▼
Outputs:
    ├──→ Patient Reply → Channel Adapter → Patient
    ├──→ EMR Draft → EMR Service → Doctor Dashboard
    ├──→ ClinicalEvent → Event Bus
    │       ├──→ Follow-up Engine (schedule)
    │       ├──→ CRM (update pipeline)
    │       ├──→ Analytics (metrics)
    │       └──→ Admin Panel (alerts if emergency)
    └──→ Memory System (persist)
```

### 5.2 Consultation-to-appointment flow

```
Medical Brain → ready_for_help_menu = true
    → Patient selects "Klinikada qabul"
        → Appointment System (find slot by specialty)
            → Billing (check payment/subscription)
                → Appointment confirmed
                    → Communication Service (reminder)
                        → CRM (pipeline: booked)
                            → Doctor Dashboard (queue updated)
```

### 5.3 Doctor review flow

```
Doctor Dashboard → EMR review view
    → Doctor edits AI draft
        → PUT /api/v1/emr/visits/{id}/review
            → EMR Service (lock final record)
                → Event: clinical.emr.reviewed
                    → Follow-up Engine (create schedule)
                    → CRM (pipeline: visit completed)
                    → Analytics (quality metrics)
```

### 5.4 Communication patterns

| Pattern | Used for | Example |
|---------|----------|---------|
| **Synchronous API** | Request/response clinical turns | Patient message → AI reply |
| **Event bus** | Async side effects | Consult completed → schedule follow-up |
| **WebSocket** | Real-time streams | Live consult, dashboard updates |
| **Cron/scheduler** | Time-based jobs | Follow-ups, reminders, eval runs |
| **Webhook** | External integrations | Payment confirmed, lab results received |

### 5.5 Dependency rules (enforced)

```
Medical Brain ──may read──→ Memory, Specialty Modules, Safety
Medical Brain ──may write──→ EMR (draft), Memory, Events
Medical Brain ──must NOT──→ Billing, Marketing, CRM directly

Billing ──must NOT──→ Medical Brain
Marketing ──may read──→ EMR summary (not internal reasoning)
Doctor Dashboard ──may read/write──→ EMR, trigger Video
Follow-up Engine ──may invoke──→ Medical Brain (follow-up mode)
All modules ──must publish──→ Events (for Analytics)
```

---

## 6. Technology Stack (Recommended)

| Layer | Year 1 | Year 3+ |
|-------|--------|---------|
| **Language** | Python (FastAPI) | + TypeScript for frontends |
| **Database** | PostgreSQL | + Redis (sessions), ClickHouse (analytics) |
| **AI** | OpenAI GPT | Multi-model router (GPT + Claude + local) |
| **Event bus** | In-process → Redis Pub/Sub | Kafka or NATS |
| **Frontend** | React/Next.js (dashboard, admin, web) | React Native (mobile) |
| **Video** | Daily.co or Twilio | Self-hosted option |
| **Storage** | Local/S3 | S3-compatible object store |
| **Deploy** | Railway → | Kubernetes (multi-region) |
| **Auth** | JWT + Telegram auth | OAuth2 + SSO for clinics |
| **Monitoring** | Logging + eval gate | Datadog/Grafana + clinical quality alerts |

---

## 7. Security, Compliance & Governance

| Area | Design |
|------|--------|
| **RBAC** | Patient / Doctor / Admin / System roles with scoped permissions |
| **Data isolation** | Multi-tenant: clinic A never sees clinic B data |
| **Audit trail** | Every EMR change, AI reasoning version, doctor override logged |
| **PHI handling** | Internal reasoning encrypted at rest; access logged |
| **AI safety** | Safety layer + emergency bypass + eval gate before deploy |
| **Consent** | Patient opts in to AI consult, data retention, follow-ups |
| **Regulatory** | Designed for HIPAA-equivalent and local health data laws |
| **Model versioning** | Every consult tagged with `model_version` + `brain_version` |

---

## 8. Five-Year Roadmap

### Year 1 (2026–2027): Foundation — "One Brain, Many Channels"

**Goal:** Production Medical Brain + Platform API + Web dashboard

| Quarter | Deliverables |
|---------|-------------|
| Q3 2026 | Medical Brain architecture finalized (this document) |
| Q3–Q4 2026 | Platform API v1, 30+ specialties, eval suite 200+ scenarios |
| Q4 2026 | Web doctor dashboard (EMR review, queue) |
| Q1 2027 | Patient web app + WhatsApp channel |
| Q2 2027 | Appointment online booking + basic billing |
| Q2 2027 | iOS/Android app v1 |
| Q3 2027 | Video consultation (basic) |
| Q4 2027 | CRM v1 + analytics dashboard |

**Success metrics:** 50+ specialties, 95%+ eval pass rate, 3+ channels live

---

### Year 2 (2027–2028): Scale — "Clinical Platform"

**Goal:** Multi-clinic, multi-doctor, full operations stack

- Multi-tenant clinic onboarding
- 50+ specialty modules with sub-specialties
- AI-assisted video consult (doctor co-pilot)
- Full billing + subscriptions
- AI Marketing v1
- Follow-up Engine: chronic disease protocols
- Multi-language (Uzbek, Russian, English)
- Evaluation suite: 500+ scenarios, automated regression CI

**Success metrics:** 10+ clinics, 1000+ consultations/month, doctor EMR review < 5 min

---

### Year 3 (2028–2029): Intelligence — "Learning Platform"

**Goal:** Platform learns from clinical patterns (privacy-preserving)

- Multi-model AI router (best model per specialty/task)
- Document intelligence (lab OCR → structured EMR)
- Predictive analytics (no-show prediction, urgency triage)
- Third-party specialty plugin marketplace
- Insurance integration (local market)
- Real-time population health dashboards
- Federated learning pilot (anonymized outcome feedback)

**Success metrics:** AI diagnostic alignment with doctors > 80%, plugin ecosystem launched

---

### Year 4 (2029–2030): Network — "Healthcare Network"

**Goal:** Platform connects clinics, labs, pharmacies, insurers

- Lab result integration (HL7/FHIR)
- E-prescription integration
- Referral network (specialist routing across clinics)
- Multi-region deployment
- Advanced CRM lifecycle automation
- AI Marketing: full lifecycle campaigns
- Regulatory certification (target markets)

**Success metrics:** Multi-country, FHIR-compliant, referral network live

---

### Year 5 (2030–2031): Standard — "Universal Medical AI"

**Goal:** The platform IS the standard for AI-assisted primary/specialty care

- 100+ specialty modules covering all board-certified domains
- Multimodal reasoning (text + image + voice + structured data)
- Real-time clinical decision support during live visits
- Outcome tracking (did the AI's differential match final diagnosis?)
- Open API for third-party health apps
- White-label platform for hospital systems
- Continuous learning with doctor feedback loop

**Success metrics:** Industry reference platform, outcome data published, white-label clients

---

## 9. Specialty Extensibility — The Core Pattern

This is the most important design decision for supporting **every** medical specialty:

```
┌─────────────────────────────────────────────┐
│           MEDICAL BRAIN (stable)            │
│  Router → Pipeline → Safety → I/O           │
└──────────────────┬──────────────────────────┘
                   │ loads at runtime
┌──────────────────▼──────────────────────────┐
│         SPECIALTY REGISTRY (grows)          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │Neurology│ │Cardiology│ │  ENT   │ ...  │
│  └────┬────┘ └────┬────┘ └────┬────┘       │
│       │           │           │             │
│  ┌────▼────┐ ┌───▼────┐ ┌───▼────┐        │
│  │headache │ │  ACS   │ │ hearing│        │
│  │ stroke  │ │heart fail│ │sinusitis│       │
│  │ vertigo │ │arrhythmia│ │  ...   │        │
│  └─────────┘ └────────┘ └────────┘        │
└─────────────────────────────────────────────┘
```

**Rules:**
1. Core engine never changes when adding a specialty
2. Each specialty is self-contained (knowledge, red flags, guidelines, referral)
3. Sub-specialties nest under parents (neurology/headache, not flat 200-item list)
4. Multi-specialty is first-class, not an edge case
5. Every specialty module includes an eval scenario pack before activation
6. Inactive modules exist in registry but are not routed until clinically validated

---

## 10. What Exists Today vs. Blueprint

| Module | Current state | Blueprint target |
|--------|--------------|-------------------|
| Medical Brain | ✅ Router + engine + 19 specialties | 100+ specialties, multi-model |
| Clinical Reasoning Engine | ✅ 7-step pipeline | Stable contract, eval-gated |
| Specialty Modules | ✅ Pluggable registry | Marketplace, sub-specialties |
| Memory System | ⚠️ Session + basic history | Full longitudinal + consent |
| EMR | ⚠️ Visit records, AI draft write | Doctor review workflow, FHIR |
| Doctor Dashboard | ⚠️ Telegram admin | Web dashboard, live queue |
| Patient App | ⚠️ Telegram bot | iOS/Android/Web native apps |
| Admin Panel | ⚠️ Telegram admin commands | Web admin panel |
| CRM | ⚠️ Patient profiles | Full lifecycle CRM |
| Appointments | ⚠️ Admin-managed | Online booking + waitlist |
| Billing | ⚠️ Basic pricing | Full payment + subscriptions |
| Video Consultation | ❌ Not started | WebRTC + AI assist |
| Follow-up Engine | ✅ Scheduler + processor | Chronic protocols |
| AI Marketing | ❌ Not started | Campaign engine |
| Analytics | ⚠️ Basic dashboard | Full BI pipeline |
| API Structure | ⚠️ Partial internal APIs | Full Platform API v1 |

---

## 11. Decision Log (Key Architectural Choices)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Clinical AI architecture | Single Medical Brain, not per-specialty bots | Consistency, evaluability, one API |
| Specialty model | Pluggable modules, not GPT fine-tunes per specialty | Faster to add, easier to evaluate |
| GPT role | Reasoning engine, not script executor | Quality, natural conversation |
| EMR generation | AI drafts, doctor confirms | Safety, regulatory compliance |
| Module communication | Events + API, not shared DB writes | Loose coupling, independent scaling |
| Channel design | Thin adapters on Platform API | One brain, infinite channels |
| Deploy gate | Eval suite must pass | Clinical quality non-negotiable |
| Billing isolation | Zero influence on clinical reasoning | Ethical, regulatory requirement |

---

## 12. Next Steps (Design Phase — No Code)

1. **Review and approve** this architecture document
2. **Define Platform API v1** OpenAPI spec (endpoints, auth, events)
3. **Design EMR doctor review workflow** (wireframes)
4. **Define specialty module certification process** (how a new specialty goes live)
5. **Plan Year 1 Q3–Q4 engineering priorities** based on Section 8
6. **Freeze Medical Brain pipeline contract** — no schema changes without eval re-run
7. **Design multi-tenant data model** for multi-clinic Year 2

---

*This document is the blueprint. Implementation follows approval, one module at a time, with evaluation gates at every clinical change.*
