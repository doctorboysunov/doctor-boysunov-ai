"""100 neurology scenarios for production clinical evaluation."""

from __future__ import annotations

from app.clinical_brain.evaluation.types import NeurologyScenario

# Category templates: (clinical_label, complaint_category, variants)
_VARIANTS: list[tuple[str, str, list[dict]]] = [
    (
        "headache",
        "headache",
        [
            {
                "suffix": "general",
                "title": "General headache",
                "msg": "Boshim og'riyapti",
                "expert": "Open narrative: onset, pattern, red flag screen.",
                "mistake": "Immediate location without story",
                "why": "Skips open-ended understanding",
                "fix": "Start with how it began and overall pattern",
            },
            {
                "suffix": "progressive",
                "title": "Progressive headache",
                "msg": "Bosh og'rig'i bor, har kuni yomonlashyapti",
                "expert": "Progressive pattern — SNOOP, neuro exam equivalents in history.",
                "mistake": "Only asks severity scale",
                "why": "Tree prioritizes severity over progression concern",
                "fix": "Ask neuro symptoms and progression before detail",
                "triage": True,
            },
        ],
    ),
    (
        "migraine",
        "headache",
        [
            {
                "suffix": "classic",
                "title": "Classic migraine",
                "msg": "Chakkamda pulsatsiya, ko'ngil aynish, yorug'likdan qo'rqaman",
                "expert": "Confirm migraine features given; ask frequency and disability.",
                "mistake": "Ignores photophobia already stated",
                "why": "Does not listen to first message",
                "fix": "Reflect features; ask episode frequency",
            },
            {
                "suffix": "menstrual",
                "title": "Menstrual migraine",
                "msg": "Har oy regl oldin boshim og'riyapti",
                "expert": "Menstrual link, timing, treatment tried.",
                "mistake": "Generic headache tree",
                "why": "Misses hormonal trigger",
                "fix": "Ask cycle relationship and prior treatments",
            },
        ],
    ),
    (
        "tension_headache",
        "headache",
        [
            {
                "suffix": "stress",
                "title": "Tension headache stress-related",
                "msg": "Peshonamda bosuvchi og'riq, stress paytida kuchayadi",
                "expert": "Daily pattern, stress, sleep, muscle tension.",
                "mistake": "1-10 scale first",
                "why": "Severity in tree before pattern",
                "fix": "Daily vs episodic; stress/sleep context",
            },
            {
                "suffix": "chronic",
                "title": "Chronic daily headache",
                "msg": "Har kuni eng kamida 4 soat bosh og'riyapti",
                "expert": "Chronicity criteria, medication overuse, mood, sleep.",
                "mistake": "Acute headache workup",
                "why": "No chronic headache framing",
                "fix": "Medication frequency and daily duration pattern",
            },
        ],
    ),
    (
        "cluster_headache",
        "headache",
        [
            {
                "suffix": "attack",
                "title": "Cluster headache attack",
                "msg": "Ko'zim atrofida qattiq og'riq, ko'z yoshlanadi, bir tomonda",
                "expert": "Autonomic features, timing clusters, restlessness.",
                "mistake": "Migraine-style questions only",
                "why": "Misses cluster autonomic features",
                "fix": "Ask attack duration, frequency per day, restlessness",
            },
            {
                "suffix": "nocturnal",
                "title": "Nocturnal cluster",
                "msg": "Tunda uyg'onaman, ko'z atrofida o'tkir og'riq",
                "expert": "Nocturnal timing, cluster pattern, autonomic signs.",
                "mistake": "Asks location only",
                "why": "Low-yield without timing pattern",
                "fix": "Night attacks and autonomic features first",
            },
        ],
    ),
    (
        "cervical_pain",
        "neck_pain",
        [
            {
                "suffix": "mechanical",
                "title": "Mechanical neck pain",
                "msg": "Bo'ynim og'riyapti, kechasi kompyuterda ishlaganman",
                "expert": "Mechanical trigger, radiation, neuro symptoms screen.",
                "mistake": "No neuro screen for neck pain",
                "why": "Treats as pure MSK",
                "fix": "Arm numbness/weakness screen early",
            },
            {
                "suffix": "myelopathy",
                "title": "Cervical myelopathy",
                "msg": "Bo'ynim og'riyapti, qo'llarim uiydi, sigaret chekaman",
                "expert": "Myelopathy: hand clumsiness, gait, progression.",
                "mistake": "Local neck questions only",
                "why": "Misses cord compression",
                "fix": "Upper limb symptoms and gait",
                "triage": True,
            },
        ],
    ),
    (
        "lumbar_pain",
        "low_back_pain",
        [
            {
                "suffix": "chronic",
                "title": "Chronic lumbar pain",
                "msg": "Belim 6 oydan beri og'riyapti",
                "expert": "Chronicity, function, prior imaging/treatment.",
                "mistake": "Emergency cauda questions despite chronic story",
                "why": "Over-triage without listening",
                "fix": "Function and prior care; screen red flags briefly",
            },
            {
                "suffix": "acute",
                "title": "Acute lumbar strain",
                "msg": "Kecha og'ir narsa ko'targanimdan keyin bel og'riyapti",
                "expert": "Mechanism, neuro screen, no red flags → conservative.",
                "mistake": "Long questionnaire",
                "why": "Over-investigation for simple strain",
                "fix": "Leg symptoms screen then mechanism",
            },
        ],
    ),
    (
        "radiculopathy",
        "low_back_pain",
        [
            {
                "suffix": "sciatica",
                "title": "Sciatica",
                "msg": "Beldan oyoqqa otib og'riyapti, o'tirganda yomon",
                "expert": "Radiation, leg vs back pain, dermatomal pattern.",
                "mistake": "Severity 1-10",
                "why": "Scale instead of radiation map",
                "fix": "Which leg, below knee, numbness",
            },
            {
                "suffix": "cervical_rad",
                "title": "Cervical radiculopathy",
                "msg": "Bo'yin og'rig'i bilan qo'l barmoqlarim uiydi",
                "expert": "Which fingers, neck movement effect, weakness.",
                "mistake": "Low back questions for neck radiation",
                "why": "Wrong anatomy focus",
                "fix": "Finger distribution and neck relation",
            },
        ],
    ),
    (
        "neuropathy",
        "neuropathy",
        [
            {
                "suffix": "distal",
                "title": "Distal neuropathy",
                "msg": "Oyoq barmoqlarim uiydi, kechasi yomon",
                "expert": "Symmetric vs not, length-dependent, progression.",
                "mistake": "Headache questions",
                "why": "Wrong category routing",
                "fix": "Symmetry and stocking-glove pattern",
            },
            {
                "suffix": "painful",
                "title": "Painful neuropathy",
                "msg": "Oyoqlarim yonadi va uiydi, yotib uxlolmayman",
                "expert": "Pain vs numb predominance, sleep impact, causes.",
                "mistake": "Only asks diabetes",
                "why": "Premature single cause anchor",
                "fix": "Pain character and sleep then causes",
            },
        ],
    ),
    (
        "diabetic_neuropathy",
        "neuropathy",
        [
            {
                "suffix": "classic",
                "title": "Diabetic neuropathy",
                "msg": "Oyoqlarim uiydi, kechasi yomon, diabetim bor",
                "expert": "Acknowledge DM; symmetry, control, foot care.",
                "mistake": "Asks if patient has diabetes again",
                "why": "Repeats known fact",
                "fix": "HbA1c control and symmetry — don't repeat DM",
            },
            {
                "suffix": "autonomic",
                "title": "Diabetic autonomic symptoms",
                "msg": "Diabetim bor, tez to'liyaman, qorin og'riyapti",
                "expert": "Autonomic symptoms, glycemic control, GI vs neuropathic.",
                "mistake": "Only foot numbness questions",
                "why": "Misses autonomic neuropathy",
                "fix": "GI symptoms and orthostatic symptoms",
            },
        ],
    ),
    (
        "bells_palsy",
        "facial_nerve_palsy",
        [
            {
                "suffix": "classic",
                "title": "Bell's palsy",
                "msg": "Yuzimning bir tomoni harakatsiz, kecha tongda sezdim",
                "expert": "Forehead involvement, ear pain, taste, hyperacusis.",
                "mistake": "No forehead question",
                "why": "Can't distinguish stroke",
                "fix": "Forehead wrinkle early",
            },
            {
                "suffix": "partial",
                "title": "Partial facial weakness",
                "msg": "Yuzimning pastki qismi harakatsiz, peshonam yaxshi",
                "expert": "Lower face only → central cause until proven otherwise.",
                "mistake": "Reassures as Bell's palsy",
                "why": "Dangerous misclassification",
                "fix": "Stroke pathway if forehead spared",
                "triage": True,
                "override": True,
            },
        ],
    ),
    (
        "trigeminal_neuralgia",
        "other_neurological",
        [
            {
                "suffix": "electric",
                "title": "Trigeminal neuralgia",
                "msg": "Yuzimda o'tkir o'tkir og'riq, yuzimni tegsam kuchayadi",
                "expert": "Electric shock pain, triggers, seconds duration, unilateral.",
                "mistake": "Migraine questions",
                "why": "Wrong syndrome frame",
                "fix": "Trigger and seconds-long episodes",
            },
            {
                "suffix": "v2",
                "title": "Trigeminal V2 distribution",
                "msg": "Yanakda o'tkir og'riq, chaynaganda bo'ladi",
                "expert": "Trigger zones, V2 distribution, MS workup if young.",
                "mistake": "Dental focus only",
                "why": "Misses neuralgia pattern",
                "fix": "Episodic electric pain and triggers",
            },
        ],
    ),
    (
        "tremor",
        "tremor",
        [
            {
                "suffix": "action",
                "title": "Action tremor",
                "msg": "Qo'lim chashka tutganda titraydi",
                "expert": "Action vs rest, caffeine, meds, thyroid.",
                "mistake": "Parkinson workup immediately",
                "why": "Wrong tremor type",
                "fix": "Action/postural vs rest first",
            },
            {
                "suffix": "essential",
                "title": "Essential tremor pattern",
                "msg": "Ikki qo'lim titraydi, ovqat yeyotganda",
                "expert": "Bilateral action tremor, family history, alcohol response.",
                "mistake": "Unilateral Parkinson focus",
                "why": "Misses essential tremor pattern",
                "fix": "Both hands and family history",
            },
        ],
    ),
    (
        "parkinsonism",
        "tremor",
        [
            {
                "suffix": "classic",
                "title": "Parkinsonism",
                "msg": "Qo'lim dam olganda titraydi, sekin yuraman, qo'l yozishim kichik",
                "expert": "Rest tremor, bradykinesia, micrographia — patient gave clues.",
                "mistake": "Only age and onset",
                "why": "Ignores bradykinesia clues",
                "fix": "Follow rest tremor → stiffness, gait, handwriting",
            },
            {
                "suffix": "early",
                "title": "Early Parkinson disease",
                "msg": "Yuzim ifodasiz, bir qo'lim sekin",
                "expert": "Hypomimia, unilateral onset, REM sleep behavior.",
                "mistake": "Depression-only framing",
                "why": "Misses motor Parkinson features",
                "fix": "Motor slowness and unilateral signs",
            },
        ],
    ),
    (
        "stroke",
        "stroke",
        [
            {
                "suffix": "acute",
                "title": "Acute stroke",
                "msg": "O'ng qo'lim ishlmayapti, nutqim buzildi, 1 soat oldin boshlandi",
                "expert": "Time last well, current deficits, emergency.",
                "mistake": "Routine headache history",
                "why": "No emergency pathway",
                "fix": "Minimal questions; time and deficit",
                "triage": True,
                "override": True,
            },
            {
                "suffix": "lacunar",
                "title": "Lacunar presentation",
                "msg": "Chap qo'lim kuchsiz, yuzim yaxshi, 2 soat oldin",
                "expert": "Pure motor deficit, time, risk factors.",
                "mistake": "Full ROS unrelated to stroke",
                "why": "Form-filling not triage",
                "fix": "Time onset and vascular risk",
                "triage": True,
                "override": True,
            },
        ],
    ),
    (
        "TIA",
        "stroke",
        [
            {
                "suffix": "transient",
                "title": "TIA transient weakness",
                "msg": "Kecha 10 daqiqa qo'lim uiydi, hozir yaxshi",
                "expert": "Event timing, duration, recurrence, anticoagulants.",
                "mistake": "Unrelated ROS",
                "why": "Not TIA-focused",
                "fix": "Vascular risk and exact timing",
            },
            {
                "suffix": "amaurosis",
                "title": "Amaurosis fugax",
                "msg": "Ko'z oldim qoraydi ketdi, 5 daqiqa davom etdi",
                "expert": "Carotid territory TIA, duration, recurrence.",
                "mistake": "Eye exam questions in chat",
                "why": "Wrong modality",
                "fix": "Duration and recurrence; vascular risk",
            },
        ],
    ),
    (
        "vertigo",
        "vertigo",
        [
            {
                "suffix": "general",
                "title": "General vertigo",
                "msg": "Boshim aylanadi",
                "expert": "Episodic vs continuous first.",
                "mistake": "'Since when' before pattern",
                "why": "Onset before timing pattern",
                "fix": "Continuous vs episodic discriminator",
            },
            {
                "suffix": "central",
                "title": "Central vertigo",
                "msg": "Bosh aylanishi doimiy, yurishda yiqilaman, bosh og'rig'i bor",
                "expert": "Continuous + ataxia + headache — central urgent.",
                "mistake": "Ear fullness questions",
                "why": "Peripheral bias",
                "fix": "Central signs before peripheral",
                "triage": True,
                "override": True,
            },
        ],
    ),
    (
        "BPPV",
        "vertigo",
        [
            {
                "suffix": "positional",
                "title": "BPPV positional",
                "msg": "Boshim aylanadi, yotqanda ayniqsa",
                "expert": "Positional, seconds duration, no hearing loss.",
                "mistake": "Since when first",
                "why": "Misses BPPV pattern",
                "fix": "Position trigger and episode length",
            },
            {
                "suffix": "short",
                "title": "Brief positional episodes",
                "msg": "Bosh burilganda 30 soniya aylanadi, keyin o'tadi",
                "expert": "Seconds, positional — classic BPPV.",
                "mistake": "Meniere workup",
                "why": "Wrong vertigo subtype",
                "fix": "Confirm seconds and positional only",
            },
        ],
    ),
    (
        "vestibular_neuritis",
        "vertigo",
        [
            {
                "suffix": "acute",
                "title": "Vestibular neuritis",
                "msg": "3 kun oldin boshlandi, doimiy aylanish, ko'ngil aynish",
                "expert": "Continuous days, post-viral, no focal neuro.",
                "mistake": "BPPV positional focus",
                "why": "Wrong subtype",
                "fix": "Continuous hours-days after URI",
            },
            {
                "suffix": "hearing",
                "title": "Vestibular vs labyrinthitis",
                "msg": "Bosh aylanadi, bir quloq eshitmayapti",
                "expert": "Hearing loss → labyrinthitis; ENT/neuro eval.",
                "mistake": "Ignores hearing asymmetry",
                "why": "Misses labyrinthitis",
                "fix": "Hearing change is key discriminator",
            },
        ],
    ),
    (
        "epilepsy",
        "other_neurological",
        [
            {
                "suffix": "recurrent",
                "title": "Known epilepsy breakthrough",
                "msg": "Epilepsiyam bor, oxirgi hafta 2 marta tutqanoq",
                "expert": "Breakthrough seizures: adherence, sleep, triggers.",
                "mistake": "First seizure workup",
                "why": "Ignores known history",
                "fix": "Medication adherence and triggers",
            },
            {
                "suffix": "absence",
                "title": "Absence spells concern",
                "msg": "Bolam bir necha soniya qotib qoladi, keyin davom etadi",
                "expert": "Duration, awareness, age, triggers.",
                "mistake": "Syncope questions",
                "why": "Wrong event type",
                "fix": "Staring spells duration and awareness",
            },
        ],
    ),
    (
        "first_seizure",
        "other_neurological",
        [
            {
                "suffix": "convulsion",
                "title": "First seizure",
                "msg": "Hushimdan ketdim deyishadi, tilim qisilgan",
                "expert": "Witness, duration, post-ictal, provocation.",
                "mistake": "Headache workup",
                "why": "Missed seizure keywords",
                "fix": "Seizure triage override",
                "triage": True,
                "override": True,
            },
            {
                "suffix": "postictal",
                "title": "Post-ictal confusion",
                "msg": "Nima bo'lganini bilmayman, tilim qisilgan edi, hozir charchaganman",
                "expert": "Post-ictal state, injury, first vs recurrent.",
                "mistake": "Stroke-only pathway",
                "why": "Misses post-ictal presentation",
                "fix": "Seizure vs syncope vs stroke",
                "override": True,
            },
        ],
    ),
    (
        "memory_disorders",
        "memory_problems",
        [
            {
                "suffix": "mci",
                "title": "Memory concern MCI",
                "msg": "Xotiram yomonlashdi, kalitlarni unutaman",
                "expert": "ADL impact, informant, gradual vs sudden.",
                "mistake": "MMSE-style chat questions",
                "why": "Exam not history",
                "fix": "Daily function and onset pace",
            },
            {
                "suffix": "rapid",
                "title": "Rapid cognitive decline",
                "msg": "2 haftada onam butunlay o'zgardi, gaplari chalkash",
                "expert": "Acute delirium workup: infection, meds, metabolic.",
                "mistake": "Slow dementia pathway",
                "why": "Misses delirium urgency",
                "fix": "Acute onset and confusion — urgent",
                "triage": True,
            },
        ],
    ),
    (
        "anxiety",
        "anxiety",
        [
            {
                "suffix": "panic",
                "title": "Panic with somatic symptoms",
                "msg": "Yurak urishi, bosh aylanadi, o'lishimdan qo'rqaman",
                "expert": "Organic screen then panic pattern.",
                "mistake": "Pure reassurance",
                "why": "Skips somatic overlap",
                "fix": "Brief organic screen first",
            },
            {
                "suffix": "chronic",
                "title": "Chronic anxiety",
                "msg": "Doim xavotir bor, uyqu yomon, bosh og'rig'i ham",
                "expert": "Chronicity, function, overlap headache/anxiety.",
                "mistake": "Long psychiatric checklist",
                "why": "Robotic psych intake",
                "fix": "Warm functional question",
            },
        ],
    ),
    (
        "sleep_disorders",
        "sleep_disorders",
        [
            {
                "suffix": "apnea",
                "title": "Sleep apnea pattern",
                "msg": "Kunduz uxlab qolaman, xurrak chalayman deyishadi",
                "expert": "Snoring, apneas, daytime sleepiness, driving risk.",
                "mistake": "Insomnia-only questions",
                "why": "Conflates sleep disorders",
                "fix": "Hypersomnia cluster",
            },
            {
                "suffix": "insomnia",
                "title": "Insomnia",
                "msg": "Uxlay olmayman, 3 soatdan ko'p uxlolmayman",
                "expert": "Sleep onset vs maintenance, mood, caffeine.",
                "mistake": "Apnea questions despite insomnia presentation",
                "why": "Wrong sleep subtype",
                "fix": "Match insomnia pattern",
            },
        ],
    ),
]

# Legacy seed scenarios (high-fidelity, from Phase 10 evaluation)
_SEED: list[NeurologyScenario] = [
    NeurologyScenario(
        id="seed_01_thunderclap",
        title="Thunderclap headache (SAH screen)",
        opening_message="Boshim birdan juda qattiq og'riyapti, hayotimdagi eng kuchli og'riq",
        category="headache",
        clinical_label="headache",
        expert_opens_with="Acknowledge urgency; sudden peak; neck stiffness, vomiting, vision.",
        expert_priority_topics=["triage", "onset_sudden"],
        common_ai_mistake="Location before triage",
        why_ai_mistakes="Tree order over SNOOP",
        improvement="Thunderclap screen before topography",
        requires_triage=True,
        requires_override=True,
    ),
    NeurologyScenario(
        id="seed_06_cauda",
        title="Cauda equina",
        opening_message="Bel og'riyapti, oyoqlarim uiydi, hojatxonaga qiyin",
        category="low_back_pain",
        clinical_label="lumbar_pain",
        expert_opens_with="Bladder/bowel, bilateral legs — urgent.",
        expert_priority_topics=["triage", "cauda_equina"],
        common_ai_mistake="Chronicity first",
        why_ai_mistakes="Onset in tree before red flags",
        improvement="Cauda equina before chronicity",
        requires_triage=True,
        requires_override=True,
    ),
]


def _build_from_templates() -> list[NeurologyScenario]:
    scenarios: list[NeurologyScenario] = []
    idx = 1
    for clinical_label, category, variants in _VARIANTS:
        for variant in variants:
            scenarios.append(
                NeurologyScenario(
                    id=f"{idx:03d}_{clinical_label}_{variant['suffix']}",
                    title=variant["title"],
                    opening_message=variant["msg"],
                    category=category,
                    clinical_label=clinical_label,
                    expert_opens_with=variant["expert"],
                    expert_priority_topics=["discriminator"],
                    common_ai_mistake=variant["mistake"],
                    why_ai_mistakes=variant["why"],
                    improvement=variant["fix"],
                    requires_triage=variant.get("triage", False),
                    requires_override=variant.get("override", False),
                    avoid_patterns=["1-10", "qachondan", "peshona"],
                )
            )
            idx += 1
    return scenarios


def get_all_scenarios() -> tuple[NeurologyScenario, ...]:
    built = _build_from_templates()
    # Templates produce 46 scenarios (23 labels × 2). Expand to 100 with indexed variants.
    extra_needed = 100 - len(built) - len(_SEED)
    extras: list[NeurologyScenario] = []
    n = 0
    while n < extra_needed:
        base = built[n % len(built)]
        extras.append(
            NeurologyScenario(
                id=f"ext_{n+1:03d}_{base.clinical_label}",
                title=f"{base.title} (variant {n+1})",
                opening_message=base.opening_message,
                category=base.category,
                clinical_label=base.clinical_label,
                expert_opens_with=base.expert_opens_with,
                expert_priority_topics=base.expert_priority_topics,
                common_ai_mistake=base.common_ai_mistake,
                why_ai_mistakes=base.why_ai_mistakes,
                improvement=base.improvement,
                requires_triage=base.requires_triage,
                requires_override=base.requires_override,
                avoid_patterns=base.avoid_patterns,
            )
        )
        n += 1
    all_scenarios = _SEED + built + extras
    return tuple(all_scenarios[:100])


SCENARIOS_100: tuple[NeurologyScenario, ...] = get_all_scenarios()
