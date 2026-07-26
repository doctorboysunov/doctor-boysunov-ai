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
    if max_sequence < 5:
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


def ensure_automatic_follow_up_plan(*, patient_id: int, anchor_date: str) -> dict:
    """Create the full automatic follow-up plan from an anchor date (idempotent if active plan exists)."""
    from app.repositories.treatment_repository import get_active_treatment

    active = get_active_treatment(patient_id)
    if active is not None:
        existing = list_follow_ups_for_treatment(active["id"])
        pending = [item for item in existing if item["status"] in {"scheduled", "notified"}]
        if pending:
            logger.info(
                "automatic_follow_up_skipped patient_id=%s treatment_id=%s pending=%s",
                patient_id,
                active["id"],
                len(pending),
            )
            return active

    return restart_automatic_follow_up_plan(patient_id=patient_id, anchor_date=anchor_date)


def restart_automatic_follow_up_plan(*, patient_id: int, anchor_date: str) -> dict:
    """Stop any pending follow-ups and start a fresh automatic plan from anchor_date."""
    from app.repositories.treatment_repository import complete_active_treatment

    active = complete_active_treatment(patient_id)
    if active is not None:
        from app.repositories.follow_up_repository import cancel_pending_follow_ups_for_treatment

        cancel_pending_follow_ups_for_treatment(int(active["id"]))

    treatment = start_patient_follow_up_schedule(patient_id=patient_id, started_at=anchor_date)
    logger.info(
        "automatic_follow_up_plan_created patient_id=%s treatment_id=%s anchor=%s",
        patient_id,
        treatment["id"],
        anchor_date,
    )
    return treatment


def stop_patient_follow_up_plan(patient_id: int) -> dict[str, int | bool]:
    """Doctor stops automatic follow-ups for a patient."""
    from app.repositories.follow_up_repository import cancel_pending_follow_ups_for_patient
    from app.repositories.treatment_repository import cancel_active_treatment

    cancelled_follow_ups = cancel_pending_follow_ups_for_patient(patient_id)
    cancelled_treatment = cancel_active_treatment(patient_id)
    logger.info(
        "follow_up_plan_stopped patient_id=%s cancelled_follow_ups=%s treatment_cancelled=%s",
        patient_id,
        cancelled_follow_ups,
        cancelled_treatment is not None,
    )
    return {
        "patient_id": patient_id,
        "cancelled_follow_ups": cancelled_follow_ups,
        "treatment_stopped": cancelled_treatment is not None,
    }


def on_visit_completed(*, patient_id: int, visit_date: str) -> dict | None:
    """Visit finished — automatically (re)create the full follow-up plan from visit date."""
    return restart_automatic_follow_up_plan(patient_id=patient_id, anchor_date=visit_date)
