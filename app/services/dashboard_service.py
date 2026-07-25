"""AI Doctor Dashboard aggregation and formatting."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.services.admin_auth import get_all_admin_telegram_ids
from app.repositories.appointment_repository import (
    list_appointments_for_date,
    list_appointments_in_range,
    list_missed_appointments,
    list_upcoming_appointments,
)
from app.repositories.communication_repository import (
    list_failed_deliveries_since,
    list_patients_without_reply,
)
from app.repositories.dashboard_repository import save_dashboard_snapshot
from app.repositories.follow_up_repository import (
    list_due_follow_ups,
    list_follow_ups_by_sequences,
    list_follow_ups_due_on,
    list_follow_ups_in_range,
)
from app.repositories.patient_intake_repository import get_patient_card, list_new_patients_since
from app.repositories.patient_profile_repository import get_patient_profile
from app.services.dashboard_actions import QUICK_ACTIONS
from app.services.dashboard_dates import range_for_period, to_iso, clinic_today

logger = logging.getLogger("doctor_boysunov.dashboard")

FOLLOW_UP_BUCKETS: dict[str, tuple[int, ...]] = {
    "10_day": (1,),
    "20_day": (2,),
    "1_month": (4,),
    "3_month_examination": (5,),
    "6_month_preventive": (6,),
}


def _patient_summary(
    *,
    patient_id: int,
    full_name: str | None = None,
    phone_number: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = get_patient_profile(patient_id)
    item = {
        "patient_id": patient_id,
        "full_name": full_name or (profile.get("full_name") if profile else None),
        "phone_number": phone_number or (profile.get("phone_number") if profile else None),
        "actions": list(QUICK_ACTIONS),
    }
    if extra:
        item.update(extra)
    return item


def _enrich_follow_ups(follow_ups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for follow_up in follow_ups:
        summary = _patient_summary(
            patient_id=follow_up["patient_id"],
            extra={
                "follow_up_id": follow_up["id"],
                "sequence_number": follow_up["sequence_number"],
                "follow_up_kind": follow_up["follow_up_kind"],
                "scheduled_date": follow_up["scheduled_date"],
                "status": follow_up["status"],
            },
        )
        enriched.append(summary)
    return enriched


def _enrich_appointments(appointments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for appointment in appointments:
        summary = _patient_summary(
            patient_id=appointment["patient_id"],
            full_name=appointment.get("patient_full_name"),
            phone_number=appointment.get("phone_number"),
            extra={
                "appointment_id": appointment["id"],
                "appointment_date": appointment["appointment_date"],
                "appointment_time": appointment["appointment_time"],
                "doctor_name": appointment["doctor_name"],
                "status": appointment["status"],
                "complaint": appointment["complaint"],
            },
        )
        enriched.append(summary)
    return enriched


def _build_statistics(
    *,
    appointments_today: list[dict],
    follow_ups_today: list[dict],
    new_patients: list[dict],
    missed: list[dict],
    non_responders: list[dict],
    high_priority: list[dict],
) -> dict[str, int]:
    return {
        "appointments_today": len(appointments_today),
        "follow_ups_today": len(follow_ups_today),
        "new_patients_today": len(new_patients),
        "missed_appointments": len(missed),
        "non_responders": len(non_responders),
        "high_priority_patients": len(high_priority),
    }


def _build_ai_recommendations(dashboard: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    stats = dashboard["statistics"]

    if stats["follow_ups_today"]:
        recommendations.append(
            f"Bugun {stats['follow_ups_today']} ta nazorat mavjud — avval ularni ko'rib chiqing."
        )
    if stats["appointments_today"]:
        recommendations.append(
            f"Bugun {stats['appointments_today']} ta qabul rejalashtirilgan."
        )
    if stats["non_responders"]:
        recommendations.append(
            f"{stats['non_responders']} ta bemor javob bermagan — qayta bog'laning."
        )
    if stats["missed_appointments"]:
        recommendations.append(
            f"{stats['missed_appointments']} ta o'tkazib yuborilgan qabul bor — qayta rejalashtiring."
        )
    if stats["high_priority_patients"]:
        recommendations.append(
            f"{stats['high_priority_patients']} ta yuqori ustuvor bemor — bugun ustuvor ishlang."
        )
    if stats["new_patients_today"]:
        recommendations.append(
            f"{stats['new_patients_today']} ta yangi bemor qo'shildi — qabul kartasini tekshiring."
        )
    if not recommendations:
        recommendations.append("Bugun navbat tartibli. Klinika statistikasi barqaror.")
    return recommendations


def build_doctor_dashboard(*, period: str = "today", anchor_date: str | None = None) -> dict[str, Any]:
    """Build live dashboard data for the requested filter period."""
    anchor = date.fromisoformat(anchor_date) if anchor_date else clinic_today()
    date_range = range_for_period(period, anchor=anchor)
    as_of = date_range.end if period in {"week", "month"} else date_range.start
    since_iso = f"{date_range.start}T00:00:00+00:00"

    appointments_today = _enrich_appointments(list_appointments_for_date(as_of))
    follow_ups_today = _enrich_follow_ups(list_follow_ups_due_on(as_of))
    follow_ups_due = _enrich_follow_ups(list_due_follow_ups(as_of_date=as_of))

    follow_up_buckets = {
        key: _enrich_follow_ups(
            list_follow_ups_by_sequences(as_of_date=as_of, sequence_numbers=sequences)
        )
        for key, sequences in FOLLOW_UP_BUCKETS.items()
    }

    new_patients = [
        _patient_summary(
            patient_id=item["patient_id"],
            full_name=item.get("full_name"),
            phone_number=item.get("phone_number"),
            extra={
                "registration_source": item.get("registration_source"),
                "created_at": item.get("created_at"),
            },
        )
        for item in list_new_patients_since(date_range.start, until_date=date_range.end)
    ]

    non_responder_ids = list_patients_without_reply(since_iso=since_iso)
    non_responders = [_patient_summary(patient_id=pid) for pid in non_responder_ids]

    missed = _enrich_appointments(list_missed_appointments(before_date=as_of))
    upcoming = _enrich_appointments(list_upcoming_appointments(from_date=as_of))

    failed_deliveries = list_failed_deliveries_since(since_iso)
    high_priority_ids: set[int] = set()
    for group in (follow_ups_due, missed, non_responders):
        for item in group:
            high_priority_ids.add(int(item["patient_id"]))
    for delivery in failed_deliveries:
        high_priority_ids.add(int(delivery["patient_id"]))

    high_priority = [_patient_summary(patient_id=pid, extra={"priority": "high"}) for pid in sorted(high_priority_ids)]

    period_appointments = _enrich_appointments(
        list_appointments_in_range(date_range.start, date_range.end)
    )
    period_follow_ups = _enrich_follow_ups(
        list_follow_ups_in_range(date_range.start, date_range.end)
    )

    statistics = _build_statistics(
        appointments_today=appointments_today,
        follow_ups_today=follow_ups_today,
        new_patients=new_patients,
        missed=missed,
        non_responders=non_responders,
        high_priority=high_priority,
    )

    dashboard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": period,
        "period_label": date_range.label,
        "date_range": {"start": date_range.start, "end": date_range.end},
        "as_of_date": as_of,
        "appointments_today": appointments_today,
        "follow_ups_today": follow_ups_today,
        "follow_ups_due": follow_ups_due,
        "follow_up_buckets": follow_up_buckets,
        "high_priority_patients": high_priority,
        "non_responders": non_responders,
        "new_patients_today": new_patients,
        "upcoming_appointments": upcoming[:20],
        "missed_appointments": missed,
        "period_appointments": period_appointments,
        "period_follow_ups": period_follow_ups,
        "statistics": statistics,
        "filters": ["today", "tomorrow", "week", "month"],
        "layout": {"desktop_columns": 2, "mobile_stack": True},
    }
    dashboard["ai_recommendations"] = _build_ai_recommendations(dashboard)
    return dashboard


def generate_morning_dashboard(*, period: str = "today") -> dict[str, Any]:
    today = to_iso(clinic_today())
    dashboard = build_doctor_dashboard(period=period, anchor_date=today)
    save_dashboard_snapshot(snapshot_date=today, period=period, payload=dashboard)
    logger.info("morning_dashboard_generated date=%s period=%s", today, period)
    return dashboard


def format_dashboard_telegram(dashboard: dict[str, Any]) -> str:
    stats = dashboard["statistics"]
    lines = [
        f"Doctor Boysunov AI — {dashboard['period_label']} Dashboard",
        f"Sana: {dashboard['as_of_date']}",
        "",
        "Statistika:",
        f"- Qabullar: {stats['appointments_today']}",
        f"- Nazoratlar: {stats['follow_ups_today']}",
        f"- Yangi bemorlar: {stats['new_patients_today']}",
        f"- Javobsiz: {stats['non_responders']}",
        f"- O'tkazilgan qabullar: {stats['missed_appointments']}",
        f"- Yuqori ustuvor: {stats['high_priority_patients']}",
        "",
        "AI tavsiyalar:",
    ]
    lines.extend(f"- {item}" for item in dashboard["ai_recommendations"][:5])

    if dashboard["appointments_today"]:
        lines.extend(["", "Bugungi qabullar:"])
        for item in dashboard["appointments_today"][:5]:
            lines.append(
                f"- #{item['patient_id']} {item.get('full_name') or 'Noma\'lum'} "
                f"{item.get('appointment_time')} ({item.get('status')})"
            )

    if dashboard["follow_ups_today"]:
        lines.extend(["", "Bugungi nazoratlar:"])
        for item in dashboard["follow_ups_today"][:5]:
            lines.append(
                f"- #{item['patient_id']} seq={item.get('sequence_number')} "
                f"{item.get('follow_up_kind')}"
            )

    lines.append("\nFiltrlar: today | tomorrow | week | month")
    lines.append("Web/Mobile: GET /api/v1/dashboard?period=today")
    return "\n".join(lines)


async def send_morning_dashboard_to_admins(bot) -> int:
    dashboard = generate_morning_dashboard(period="today")
    text = format_dashboard_telegram(dashboard)
    sent = 0
    for admin_id in get_all_admin_telegram_ids():
        await bot.send_message(chat_id=admin_id, text=text)
        sent += 1
    logger.info("morning_dashboard_sent admin_count=%s", sent)
    return sent
