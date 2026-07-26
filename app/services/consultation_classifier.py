"""Detect neurological complaint category from patient text."""

from __future__ import annotations

import re

from app.domain.consultation import COMPLAINT_LABELS, ComplaintCategory

_CATEGORY_PATTERNS: dict[ComplaintCategory, tuple[str, ...]] = {
    "stroke": (
        r"insult",
        r"stroke",
        r"falaj",
        r"qotib qol",
        r"nutq buzil",
        r"yuz qismi qaltir",
        r"sudden weakness",
        r"qo['']?l kuchsiz",
        r"oyoq kuchsiz",
        r"yarim tan",
    ),
    "facial_nerve_palsy": (
        r"yuz qiyshay",
        r"yuz qiysh",
        r"bell",
        r"yuz nerv",
        r"lab tush",
        r"ko['']?z qisib",
        r"facial palsy",
    ),
    "headache": (
        r"bosh\s*og['']?ri",
        r"boshim\s*og['']?ri",
        r"headache",
        r"migren",
        r"migraine",
        r"peshon",
        r"chakka\s*og['']?ri",
    ),
    "low_back_pain": (
        r"bel\s*og['']?ri",
        r"belim\s*og['']?ri",
        r"orqa\s*og['']?ri",
        r"lumbar",
        r"low back",
        r"qorin\s*og['']?ri\s*emas.*bel",
        r"bel\s*og['']?ri",
        r"chap\s+oyoq.*og['']?ri",
        r"o['']?ng\s+oyoq.*og['']?ri",
        r"oyoq\s*og['']?ri",
        r"leg\s*pain",
        r"left\s+leg",
        r"right\s+leg",
        r"sciatica",
        r"iqtiroiyog['']?riq",
    ),
    "neck_pain": (
        r"bo['']?yin\s*og['']?ri",
        r"bo['']?ynim\s*og['']?ri",
        r"servikal",
        r"neck pain",
        r"bo['']?yin\s*qot",
    ),
    "vertigo": (
        r"bosh\s*aylan",
        r"vertigo",
        r"vertikal",
        r"qaltirab tur",
        r"stagger",
        r"balance",
        r"muvozanat",
    ),
    "neuropathy": (
        r"neuropat",
        r"uvish",
        r"sezgi\s*pasay",
        r"tingling",
        r"numbness",
        r"qo['']?l\s*uvish",
        r"oyoq\s*uvish",
        r"sezgi\s*buzil",
    ),
    "tremor": (
        r"titroq",
        r"tremor",
        r"qaltirash",
        r"titray",
        r"titro",
        r"qo['']?l\s*tit",
        r"harakatda\s*tit",
    ),
    "memory_problems": (
        r"xotira",
        r"memory",
        r"esdan\s*chiq",
        r"unut",
        r"demens",
        r"dementia",
        r"kognitiv",
    ),
    "sleep_disorders": (
        r"uyqu",
        r"sleep",
        r"uxlamay",
        r"uxlay olmay",
        r"insomnia",
        r"uxlab\s*olmay",
        r"ertalab\s*uyg'on",
        r"snoring",
        r"xurillash",
    ),
    "anxiety": (
        r"xavotir",
        r"tashvish",
        r"anxiety",
        r"panic",
        r"panika",
        r"asabiylash",
        r"stress",
    ),
    "depression": (
        r"depress",
        r"depres",
        r"ko['']?ngil\s*siq",
        r"umidsiz",
        r"happy\s*emas",
        r"ruh\s*iy\s*pasay",
    ),
    "other_neurological": (
        r"nevrolog",
        r"asab",
        r"seizure",
        r"tutqanoq",
        r"epilep",
        r"shikoyat",
    ),
}

_PRIORITY: tuple[ComplaintCategory, ...] = (
    "stroke",
    "facial_nerve_palsy",
    "headache",
    "low_back_pain",
    "neck_pain",
    "vertigo",
    "neuropathy",
    "tremor",
    "memory_problems",
    "sleep_disorders",
    "anxiety",
    "depression",
    "other_neurological",
)


def classify_complaint(text: str | None) -> ComplaintCategory:
    normalized = (text or "").strip().lower()
    if not normalized:
        return "other_neurological"

    scores: dict[ComplaintCategory, int] = {}
    for category, patterns in _CATEGORY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, normalized):
                score += 1
        if score:
            scores[category] = score

    if not scores:
        return "neuropathy"  # neutral clinical category — syndrome from reasoner, not this label

    best_score = max(scores.values())
    candidates = [cat for cat, score in scores.items() if score == best_score]
    for category in _PRIORITY:
        if category in candidates:
            return category
    return candidates[0]


def complaint_label(category: ComplaintCategory) -> str:
    return COMPLAINT_LABELS.get(category, category)
