"""Dashboard date range helpers and filter periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

FilterPeriod = str  # today | tomorrow | week | month


@dataclass(frozen=True)
class DateRange:
    start: str
    end: str
    label: str


def clinic_today() -> date:
    return date.today()


def to_iso(value: date) -> str:
    return value.isoformat()


def range_for_period(period: FilterPeriod, *, anchor: date | None = None) -> DateRange:
    base = anchor or clinic_today()
    if period == "today":
        iso = to_iso(base)
        return DateRange(start=iso, end=iso, label="Bugun")
    if period == "tomorrow":
        tomorrow = base + timedelta(days=1)
        iso = to_iso(tomorrow)
        return DateRange(start=iso, end=iso, label="Ertaga")
    if period == "week":
        start = base - timedelta(days=base.weekday())
        end = start + timedelta(days=6)
        return DateRange(start=to_iso(start), end=to_iso(end), label="Bu hafta")
    if period == "month":
        start = base.replace(day=1)
        if base.month == 12:
            next_month = base.replace(year=base.year + 1, month=1, day=1)
        else:
            next_month = base.replace(month=base.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return DateRange(start=to_iso(start), end=to_iso(end), label="Bu oy")
    raise ValueError(f"Invalid dashboard period: {period!r}")
