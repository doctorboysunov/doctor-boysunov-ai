"""Medical knowledge reference — question trees as guidance, not scripts."""

from __future__ import annotations

from app.domain.consultation import ComplaintCategory
from app.services.consultation_classifier import complaint_label
from app.services.consultation_question_trees import get_questions_for_category


def format_knowledge_reference(category: ComplaintCategory) -> str:
    """Export question tree topics as reference material for GPT reasoning."""
    questions = get_questions_for_category(category)
    if not questions:
        return "Umumiy nevrologik anamnez mavzulari: boshlanish, kuch, xarakter, progressiya, qo'shimcha belgilar."

    lines = [
        f"Tibbiy ma'lumot namunasi ({complaint_label(category)}) — FAQAT ma'lumot uchun, majburiy tartib EMAS:",
    ]
    for question in questions:
        marker = "muhim" if question.required else "qo'shimcha"
        red_flag = f" [qizil bayroq: {question.red_flag_label}]" if question.red_flag_label else ""
        lines.append(f"- {question.id}: {question.text} ({marker}){red_flag}")
    lines.append(
        "Bu ro'yxatdan fikrlab tanlang — bemorning javoblariga qarab moslashtiring. "
        "Ikki bemorga bir xil savol bermang."
    )
    return "\n".join(lines)
