"""Generate and extend follow-up schedules for treatments."""

from __future__ import annotations

import logging

from app.repositories.follow_up_repository import (
    create_follow_up,
    list_follow_ups_for_treatment,
)
from app.repositories.treatment_repository import get_treatment
from app.services.follow_up_messages import build_follow_up_message
from app.services.follow_up_scheduler import (
    build_initial_follow_up_dates,
    build_recurring_follow_up_date,
    parse_iso_date,
    to_iso_date,
)

logger = logging.getLogger("doctor_boysunov.follow_up_planner")


def generate_initial_follow_up_schedule(treatment_id: int) -> list[dict]:
    treatment = get_treatment(treatment_id)
    if treatment is None:
        raise ValueError(f"Treatment not found: {treatment_id}")

    start_date = parse_iso_date(treatment["started_at"])
    planned = build_initial_follow_up_dates(start_date)
    created: list[dict] = []

    for sequence_number, scheduled_date, kind in planned:
        message = build_follow_up_message(
            kind,
            sequence_number=sequence_number,
            scheduled_date=to_iso_date(scheduled_date),
        )
        follow_up = create_follow_up(
            patient_id=treatment["patient_id"],
            treatment_id=treatment_id,
            sequence_number=sequence_number,
            follow_up_kind=kind,
            scheduled_date=to_iso_date(scheduled_date),
            invitation_text=message,
        )
        created.append(follow_up)

    schedule_next_recurring_if_missing(treatment_id)
    return created


def schedule_next_recurring_if_missing(treatment_id: int) -> dict | None:
    """Schedule the next 6-month follow-up after step 6+ if not already present."""
    treatment = get_treatment(treatment_id)
    if treatment is None:
        raise ValueError(f"Treatment not found: {treatment_id}")

    existing = list_follow_ups_for_treatment(treatment_id)
    if not existing:
        return None

    max_sequence = max(item["sequence_number"] for item in existing)
    if max_sequence < 6:
        return None
    if any(item["sequence_number"] == max_sequence + 1 for item in existing):
        return None

    latest = max(existing, key=lambda item: item["sequence_number"])
    previous_date = parse_iso_date(latest["scheduled_date"])
    next_date = build_recurring_follow_up_date(previous_date)
    next_sequence = max_sequence + 1

    message = build_follow_up_message(
        "preventive",
        sequence_number=next_sequence,
        scheduled_date=to_iso_date(next_date),
    )
    follow_up = create_follow_up(
        patient_id=treatment["patient_id"],
        treatment_id=treatment_id,
        sequence_number=next_sequence,
        follow_up_kind="preventive",
        scheduled_date=to_iso_date(next_date),
        invitation_text=message,
    )
    logger.info(
        "schedule_next_recurring treatment_id=%s sequence=%s date=%s",
        treatment_id,
        next_sequence,
        follow_up["scheduled_date"],
    )
    return follow_up


def start_patient_follow_up_schedule(*, patient_id: int, started_at: str) -> dict:
    from app.repositories.treatment_repository import create_treatment

    treatment = create_treatment(patient_id=patient_id, started_at=started_at)
    generate_initial_follow_up_schedule(treatment["id"])
    return treatment
