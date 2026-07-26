"""Clinical guidelines reference — inform reasoning, never replace it."""

from __future__ import annotations

from app.domain.consultation import ComplaintCategory

_GUIDELINES: dict[str, str] = {
    "headache": (
        "Guideline-informed reasoning (NOT a script): ICHD headache red flags (SNOOP4); "
        "thunderclap → subarachnoid hemorrhage until excluded; new headache >50 urgent eval."
    ),
    "low_back_pain": (
        "Red flags: cauda equina (urinary retention, saddle anesthesia, bilateral leg weakness), "
        "fever, trauma, cancer history, IV drug use, progressive deficit."
    ),
    "neck_pain": (
        "Red flags: myelopathy (hand clumsiness, gait, Lhermitte), trauma, fever, progressive deficit."
    ),
    "vertigo": (
        "Distinguish central vs peripheral: continuous vertigo + neuro signs → central (HINTS concept). "
        "BPPV: brief positional seconds. Vestibular neuritis: continuous days post-viral."
    ),
    "stroke": (
        "Time is brain: last known well, thrombolysis/thrombectomy windows. "
        "TIA: high early stroke risk — vascular workup."
    ),
    "neuropathy": (
        "Length-dependent symmetric → metabolic/toxic. Asymmetric → radiculopathy/compression. "
        "Rapid progression → inflammatory or compressive urgency."
    ),
    "facial_nerve_palsy": (
        "Forehead sparing → central facial palsy (stroke) until proven otherwise. "
        "Bell's palsy: full unilateral face including forehead."
    ),
    "tremor": (
        "Rest tremor + bradykinesia → parkinsonism. Action/postural → essential or enhanced physiologic."
    ),
    "memory_problems": (
        "Acute confusion → delirium workup. Subacute progressive → neurodegenerative. "
        "Always assess functional impact and informant history."
    ),
    "sleep_disorders": (
        "Obstructive sleep apnea: snoring, witnessed apneas, daytime sleepiness. "
        "Do not conflate with primary insomnia."
    ),
    "anxiety": (
        "Somatic symptoms require brief organic rule-out before attributing to anxiety."
    ),
    "depression": (
        "Safety assessment; distinguish from hypothyroidism, sleep apnea, neurologic disease."
    ),
    "other_neurological": (
        "Seizure first presentation: witness, duration, post-ictal, tongue bite, provocation."
    ),
}


def format_guidelines_reference(category: ComplaintCategory) -> str:
    text = _GUIDELINES.get(category, _GUIDELINES["other_neurological"])
    return (
        "CLINICAL GUIDELINES (inform hypotheses and triage — NOT a script; GPT still decides each question):\n"
        f"{text}"
    )
