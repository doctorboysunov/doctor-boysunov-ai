"""Specialty module base — each specialty is a pluggable knowledge unit."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.medical import MedicalSpecialty


@dataclass(frozen=True)
class SpecialtyModule:
    """One medical specialty — knowledge, red flags, referral, investigations."""

    id: MedicalSpecialty
    label: str
    patterns: tuple[str, ...]
    knowledge: str
    guidelines: str
    red_flags: tuple[str, ...]
    referral_rules: tuple[str, ...]
    investigation_suggestions: tuple[str, ...]
    expert_priorities: tuple[str, ...]
    avoid_early: tuple[str, ...] = ()
    priority: int = 50  # higher = preferred in tie-break

    def format_reference_block(self) -> str:
        lines = [
            f"=== {self.label.upper()} REFERENCE (inform reasoning — NOT a script) ===",
            f"Knowledge: {self.knowledge}",
            f"Guidelines: {self.guidelines}",
        ]
        if self.red_flags:
            lines.append(f"Red flags: {'; '.join(self.red_flags)}")
        if self.expert_priorities:
            lines.append(f"High-yield priorities: {'; '.join(self.expert_priorities)}")
        if self.avoid_early:
            lines.append(f"Avoid early: {'; '.join(self.avoid_early)}")
        if self.referral_rules:
            lines.append(f"Referral: {'; '.join(self.referral_rules)}")
        if self.investigation_suggestions:
            lines.append(f"Investigations (internal): {'; '.join(self.investigation_suggestions)}")
        return "\n".join(lines)
