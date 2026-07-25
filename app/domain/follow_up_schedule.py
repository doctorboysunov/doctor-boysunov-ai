"""Follow-up schedule definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OffsetUnit = Literal["days", "months"]

FOLLOW_UP_STATUSES = ("scheduled", "notified", "completed", "cancelled")

FOLLOW_UP_KINDS = ("check_in", "examination", "preventive")


@dataclass(frozen=True)
class ScheduleOffset:
    amount: int
    unit: OffsetUnit
    kind: str


# Exact sequence: steps 1-6, then repeat step 6 interval forever.
INITIAL_FOLLOW_UP_SCHEDULE: tuple[ScheduleOffset, ...] = (
    ScheduleOffset(10, "days", "check_in"),       # 1: 10 days after treatment
    ScheduleOffset(10, "days", "check_in"),       # 2: 10 days after previous
    ScheduleOffset(10, "days", "check_in"),       # 3: 10 days after previous
    ScheduleOffset(1, "months", "check_in"),      # 4: 1 month after previous
    ScheduleOffset(3, "months", "examination"),    # 5: 3 months — examination invite
    ScheduleOffset(6, "months", "preventive"),     # 6: 6 months — preventive invite
)

RECURRING_FOLLOW_UP_OFFSET = ScheduleOffset(6, "months", "preventive")

RECURRING_START_SEQUENCE = len(INITIAL_FOLLOW_UP_SCHEDULE) + 1  # 7
