"""Appointment date helpers for admin views."""

from datetime import date, timedelta


def clinic_today_iso() -> str:
    return date.today().isoformat()


def clinic_tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()
