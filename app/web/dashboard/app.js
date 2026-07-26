const state = {
  apiKey: localStorage.getItem("medical_os_api_key") || "",
  visits: [],
  selectedVisitId: null,
};

const $ = (id) => document.getElementById(id);

function headers() {
  return {
    "Content-Type": "application/json",
    "X-API-Key": state.apiKey,
  };
}

async function api(path, options = {}) {
  const res = await fetch(`/api/v1${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

function urgencyClass(level) {
  const v = (level || "routine").toLowerCase();
  if (v === "emergency" || v === "urgent") return v;
  return "routine";
}

function renderQueue() {
  const list = $("reviewQueue");
  list.innerHTML = "";
  if (!state.visits.length) {
    list.innerHTML = "<li class='hint'>No pending AI reviews</li>";
    return;
  }
  state.visits.forEach((visit) => {
    const li = document.createElement("li");
    li.className = "queue-item" + (visit.id === state.selectedVisitId ? " active" : "");
    const assessment = visit.ai_assessment || {};
    const emr = assessment.doctor_emr || {};
    li.innerHTML = `
      <div class="name">${visit.patient_name || "Patient #" + visit.patient_id}</div>
      <div class="meta">${emr.chief_complaint || visit.main_complaint || "Consultation"} · ${visit.visit_date}</div>
    `;
    li.onclick = () => selectVisit(visit.id);
    list.appendChild(li);
  });
}

function renderVisit(visit) {
  $("emptyState").classList.add("hidden");
  $("reviewPanel").classList.remove("hidden");

  const assessment = visit.ai_assessment || {};
  const emr = assessment.doctor_emr || {};
  const brain = assessment.medical_brain || {};
  const reasoning = assessment.internal_reasoning || {};

  $("patientName").textContent = visit.patient_name || `Patient #${visit.patient_id}`;
  $("visitMeta").textContent = `Visit #${visit.id} · ${visit.visit_date} · ${visit.ai_review_status}`;
  $("chiefComplaint").textContent = emr.chief_complaint || visit.main_complaint || "—";

  const primary = visit.primary_specialty || assessment.primary_specialty || "—";
  const secondary = visit.secondary_specialties || assessment.secondary_specialties || [];
  $("specialties").textContent = secondary.length ? `${primary} + ${secondary.join(", ")}` : primary;

  const badge = $("urgencyBadge");
  badge.textContent = visit.urgency || emr.urgency || "routine";
  badge.className = "badge " + urgencyClass(badge.textContent);

  const diffList = $("differentials");
  diffList.innerHTML = "";
  (emr.differential_diagnoses || []).forEach((d) => {
    const li = document.createElement("li");
    li.textContent = d;
    diffList.appendChild(li);
  });

  const flagsList = $("redFlags");
  flagsList.innerHTML = "";
  (emr.red_flags_noted || brain.step4_red_flags || []).forEach((f) => {
    const li = document.createElement("li");
    li.textContent = f;
    flagsList.appendChild(li);
  });

  const reasoningLines = [];
  if (brain.step1_patient_meaning) reasoningLines.push("Meaning: " + brain.step1_patient_meaning);
  if (brain.step3_hypotheses) {
    brain.step3_hypotheses.forEach((h) => {
      reasoningLines.push(`• ${h.name} (${h.probability}): ${h.rationale || ""}`);
    });
  }
  if (brain.step6_next_question_rationale) reasoningLines.push("Next Q: " + brain.step6_next_question_rationale);
  if (reasoning.next_question_rationale) reasoningLines.push("Rationale: " + reasoning.next_question_rationale);
  $("aiReasoning").textContent = reasoningLines.join("\n") || "No reasoning recorded";

  const form = $("reviewForm");
  form.preliminary_diagnosis.value = visit.preliminary_diagnosis || emr.differential_diagnoses?.[0] || "";
  form.final_diagnosis.value = visit.final_diagnosis || "";
  form.treatment_plan.value = visit.treatment_plan || emr.clinical_notes || "";
  form.examination_findings.value = visit.examination_findings || "";
  form.notes.value = visit.notes || "";
}

async function selectVisit(visitId) {
  state.selectedVisitId = visitId;
  renderQueue();
  const visit = state.visits.find((v) => v.id === visitId);
  if (visit) renderVisit(visit);
}

async function loadDashboard() {
  const [pending, dash, info] = await Promise.all([
    api("/emr/reviews/pending"),
    api("/dashboard?period=today"),
    api("/platform/info"),
  ]);
  state.visits = pending.visits || [];
  renderQueue();

  const stats = $("todayStats");
  const s = dash.statistics || {};
  stats.innerHTML = `
    <div class="stat"><strong>${pending.count}</strong> AI reviews pending</div>
    <div class="stat"><strong>${s.appointments_today || 0}</strong> Appointments today</div>
    <div class="stat"><strong>${s.follow_ups_due || 0}</strong> Follow-ups due</div>
  `;
  $("platformInfo").textContent = `${info.name} v${info.version} · Brain ${info.medical_brain_contract}`;
}

async function connect() {
  state.apiKey = $("apiKey").value.trim();
  localStorage.setItem("medical_os_api_key", state.apiKey);
  await loadDashboard();
}

$("connectBtn").onclick = connect;
$("apiKey").value = state.apiKey;

$("reviewForm").onsubmit = async (e) => {
  e.preventDefault();
  if (!state.selectedVisitId) return;
  const form = e.target;
  const payload = {
    doctor_id: form.doctor_id.value,
    preliminary_diagnosis: form.preliminary_diagnosis.value || null,
    final_diagnosis: form.final_diagnosis.value || null,
    treatment_plan: form.treatment_plan.value || null,
    examination_findings: form.examination_findings.value || null,
    notes: form.notes.value || null,
    approve: true,
  };
  await api(`/emr/visits/${state.selectedVisitId}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedVisitId = null;
  $("reviewPanel").classList.add("hidden");
  $("emptyState").classList.remove("hidden");
  await loadDashboard();
};

if (state.apiKey) {
  loadDashboard().catch(() => {});
}
