"""Follow-up schedule definitions — Phase 9.5 automatic plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OffsetUnit = Literal["days", "months"]

FOLLOW_UP_STATUSES = ("scheduled", "notified", "completed", "cancelled", "no_response")

FOLLOW_UP_KINDS = ("check_in", "examination", "preventive")


@dataclass(frozen=True)
class ScheduleOffset:
    amount: int
    unit: OffsetUnit
    kind: str


# Absolute offsets from treatment / visit anchor date.
# Day 10, Day 20, Day 30, Month 3, Month 6 — then +6 months forever.
INITIAL_FOLLOW_UP_SCHEDULE: tuple[ScheduleOffset, ...] = (
    ScheduleOffset(10, "days", "check_in"),        # 1: Day 10
    ScheduleOffset(20, "days", "check_in"),        # 2: Day 20
    ScheduleOffset(30, "days", "check_in"),        # 3: Day 30
    ScheduleOffset(3, "months", "examination"),    # 4: Month 3 — return examination
    ScheduleOffset(6, "months", "preventive"),     # 5: Month 6 — preventive treatment
)

RECURRING_FOLLOW_UP_OFFSET = ScheduleOffset(6, "months", "preventive")

RECURRING_START_SEQUENCE = len(INITIAL_FOLLOW_UP_SCHEDULE) + 1  # 6
