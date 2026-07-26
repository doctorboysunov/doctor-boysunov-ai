"""Compute follow-up dates from the clinic schedule."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from app.domain.follow_up_schedule import (
    INITIAL_FOLLOW_UP_SCHEDULE,
    RECURRING_FOLLOW_UP_OFFSET,
    ScheduleOffset,
)


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def to_iso_date(value: date) -> str:
    return value.isoformat()


def add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base.day, last_day)
    return date(year, month, day)


def apply_offset(base: date, offset: ScheduleOffset) -> date:
    if offset.unit == "days":
        return base + timedelta(days=offset.amount)
    return add_months(base, offset.amount)


def build_initial_follow_up_dates(treatment_start: date) -> list[tuple[int, date, str]]:
    """Return (sequence_number, scheduled_date, kind) for steps 1-5 from anchor date."""
    results: list[tuple[int, date, str]] = []

    for index, step in enumerate(INITIAL_FOLLOW_UP_SCHEDULE, start=1):
        scheduled = apply_offset(treatment_start, step)
        results.append((index, scheduled, step.kind))

    return results


def build_recurring_follow_up_date(previous_scheduled: date) -> date:
    return apply_offset(previous_scheduled, RECURRING_FOLLOW_UP_OFFSET)


def next_recurring_sequence(existing_max_sequence: int) -> int:
    from app.domain.follow_up_schedule import RECURRING_START_SEQUENCE

    return max(existing_max_sequence + 1, RECURRING_START_SEQUENCE)
