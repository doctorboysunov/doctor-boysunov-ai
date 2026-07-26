"""Detect red-flag symptoms that require emergency care."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedFlagRule:
    code: str
    patterns: tuple[str, ...]
    label: str


RED_FLAG_RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule(
        "stroke",
        (
            r"insult",
            r"stroke",
            r"falaj",
            r"yuz qismi qaltir",
            r"nutq buzil",
            r"gap.*buzil",
            r"qo['']?l.*ishlamay",
            r"kuchsiz",
            r"sudden weakness",
        ),
        "possible stroke",
    ),
    RedFlagRule(
        "chest_pain",
        (
            r"ko['']?krak\s+og['']?ri",
            r"ko['']?kragim\s+og['']?ri",
            r"chest pain",
            r"yurak og['']?rig",
            r"ko['']?krakda bosim",
        ),
        "chest pain",
    ),
    RedFlagRule(
        "breathing",
        (
            r"nafas qisil",
            r"nafas olish qiyin",
            r"severe breathing",
            r"can['']?t breathe",
            r"bo['']?g['']?il qisil",
        ),
        "severe breathing difficulty",
    ),
    RedFlagRule(
        "seizure",
        (
            r"tutqanoq",
            r"seizure",
            r"convulsion",
            r"fit bor",
        ),
        "seizure",
    ),
    RedFlagRule(
        "consciousness",
        (
            r"hushdan ket",
            r"hushini yo['']?qot",
            r"loss of consciousness",
            r" unconscious",
            r"hushsiz",
        ),
        "loss of consciousness",
    ),
    RedFlagRule(
        "bleeding",
        (
            r"kuchli qon ket",
            r"severe bleeding",
            r"to['']?xta qon ket",
            r"qon ketish to['']?xtab",
            r"qorong['']?u axlat",
            r"qorong['']?u rangli",
            r"melena",
        ),
        "GI bleeding",
    ),
    RedFlagRule(
        "hemoptysis",
        (
            r"qizil qon",
            r"qon tufla",
            r"hemoptysis",
            r"yo['']?tal.*qon|qon.*yo['']?tal",
        ),
        "hemoptysis",
    ),
    RedFlagRule(
        "weight_loss",
        (
            r"vazn.*yo['']?qot",
            r"weight loss",
            r"kg yo['']?qot",
        ),
        "unexplained weight loss",
    ),
    RedFlagRule(
        "cellulitis",
        (
            r"qizarish kengay",
            r"tarqal.*qizarish",
            r"spreading redness",
        ),
        "spreading cellulitis",
    ),
    RedFlagRule(
        "drug_rash",
        (
            r"tozma.*isitma|isitma.*tozma",
            r"butun tana.*tozma",
            r"ko['']?z.*qizarib",
            r"amoxicillin|antibiotik",
        ),
        "drug rash",
    ),
    RedFlagRule(
        "infant_fever",
        (
            r"haftalik.*isitma|isitma.*haftalik",
            r"oylik.*isitma",
            r"chaqaloq.*isitma",
            r"8 haftalik",
        ),
        "infant fever",
    ),
)


def detect_red_flags(message: str) -> list[str]:
    text = message.lower()
    matched: list[str] = []
    for rule in RED_FLAG_RULES:
        if any(re.search(pattern, text) for pattern in rule.patterns):
            matched.append(rule.code)
    return matched


def build_emergency_response(red_flags: list[str]) -> str:
    labels = []
    code_to_label = {rule.code: rule.label for rule in RED_FLAG_RULES}
    for code in red_flags:
        labels.append(code_to_label.get(code, code))

    symptoms = ", ".join(labels)
    return (
        "Bu belgilar shoshilinch tibbiy yordamni talab qilishi mumkin.\n\n"
        f"Ko'rsatilgan xavfli belgilar: {symptoms}.\n\n"
        "Iltimos, hozir 103 raqamiga qo'ng'iroq qiling yoki eng yaqin shoshilinch yordam xizmatiga murojaat qiling.\n"
        "Onlayn maslahat yoki offline konsultatsiya shoshilinch holatda birinchi navbatda emas — avvalo favqulodda yordam kerak.\n\n"
        "Xavf o'tgach, Doctor Boysunov bilan onlayn yoki offline konsultatsiya bron qilishingiz mumkin."
    )
