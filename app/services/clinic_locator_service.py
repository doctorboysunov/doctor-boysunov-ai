"""AI Clinic Locator — rank clinics and suggest appointment times."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

from app.domain.clinic import APPOINTMENT_SLOT_MINUTES, ROLE_PRIORITY, WEEKDAY_KEYS
from app.repositories.appointment_repository import list_appointments_for_clinic_on_date
from app.repositories.clinic_repository import list_clinic_locations
from app.repositories.patient_profile_repository import get_patient_profile
from app.services.appointment_dates import clinic_today_iso

logger = logging.getLogger("doctor_boysunov.clinic_locator")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _weekday_key(for_date: str) -> str:
    weekday = date.fromisoformat(for_date).weekday()
    return WEEKDAY_KEYS[weekday]


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%H:%M")


def _format_time(value: datetime) -> str:
    return value.strftime("%H:%M")


def _is_working_on_date(clinic: dict[str, Any], for_date: str) -> bool:
    working_days = {day.strip().lower() for day in (clinic.get("working_days") or "").split(",") if day.strip()}
    return _weekday_key(for_date) in working_days


def _generate_time_slots(clinic: dict[str, Any]) -> list[str]:
    start = _parse_time(clinic["working_hours_start"])
    end = _parse_time(clinic["working_hours_end"])
    slots: list[str] = []
    current = start
    step = timedelta(minutes=APPOINTMENT_SLOT_MINUTES)
    while current + step <= end:
        slots.append(_format_time(current))
        current += step
    return slots


def get_available_appointment_times(
    clinic: dict[str, Any],
    *,
    appointment_date: str,
) -> list[str]:
    if not _is_working_on_date(clinic, appointment_date):
        return []

    all_slots = _generate_time_slots(clinic)
    booked = {
        item["appointment_time"]
        for item in list_appointments_for_clinic_on_date(
            clinic["id"],
            appointment_date,
        )
        if item.get("status") in {"pending", "confirmed"}
    }
    return [slot for slot in all_slots if slot not in booked]


def _patient_coordinates(patient_id: int) -> tuple[float | None, float | None]:
    profile = get_patient_profile(patient_id)
    if profile is None:
        return None, None
    lat = profile.get("latitude")
    lon = profile.get("longitude")
    if lat is None or lon is None:
        return None, None
    return float(lat), float(lon)


def _distance_for_patient(clinic: dict[str, Any], patient_id: int) -> float | None:
    lat, lon = _patient_coordinates(patient_id)
    if lat is None or lon is None:
        return None
    return haversine_km(lat, lon, clinic["latitude"], clinic["longitude"])


def _specialty_matches(clinic: dict[str, Any], specialty: str | None) -> bool:
    if not specialty:
        return True
    clinic_specialty = (clinic.get("specialty") or "").strip().lower()
    if not clinic_specialty:
        return True
    return specialty.strip().lower() in clinic_specialty or clinic_specialty in specialty.strip().lower()


def _score_candidate(
    clinic: dict[str, Any],
    *,
    patient_id: int,
    appointment_date: str,
    specialty: str | None,
) -> dict[str, Any] | None:
    if not clinic.get("is_active"):
        return None
    if not _specialty_matches(clinic, specialty):
        return None

    available_times = get_available_appointment_times(clinic, appointment_date=appointment_date)
    working_today = _is_working_on_date(clinic, appointment_date)
    distance_km = _distance_for_patient(clinic, patient_id)

    return {
        "clinic": clinic,
        "available_appointment_times": available_times,
        "working_today": working_today,
        "has_availability": working_today and len(available_times) > 0,
        "distance_km": distance_km,
        "role_priority": ROLE_PRIORITY.get(clinic["role"], 99),
    }


def _build_recommendation(candidate: dict[str, Any], *, fallback_used: bool) -> dict[str, Any]:
    clinic = candidate["clinic"]
    distance = candidate["distance_km"]
    return {
        "clinic_location_id": clinic["id"],
        "clinic_name": clinic["clinic_name"],
        "staff_name": clinic["staff_name"],
        "doctor_or_student_name": clinic["staff_name"],
        "role": clinic["role"],
        "specialty": clinic.get("specialty"),
        "address": clinic["address"],
        "phone": clinic.get("phone"),
        "google_maps_link": clinic.get("google_maps_link"),
        "services": clinic.get("services"),
        "working_days": clinic.get("working_days"),
        "working_hours": f"{clinic.get('working_hours_start')}-{clinic.get('working_hours_end')}",
        "distance_km": round(distance, 2) if distance is not None else None,
        "available_appointment_times": candidate["available_appointment_times"],
        "fallback_used": fallback_used,
        "recommended_date": None,
    }


def recommend_clinic_for_patient(
    patient_id: int,
    *,
    specialty: str | None = None,
    appointment_date: str | None = None,
) -> dict[str, Any] | None:
    """Choose the best clinic location for a patient appointment recommendation."""
    target_date = appointment_date or clinic_today_iso()
    clinics = list_clinic_locations(active_only=True)
    if not clinics:
        return None

    candidates = [
        scored
        for clinic in clinics
        if (scored := _score_candidate(clinic, patient_id=patient_id, appointment_date=target_date, specialty=specialty))
        is not None
    ]
    if not candidates:
        return None

    available_doctors = [
        c for c in candidates if c["clinic"]["role"] == "doctor" and c["has_availability"]
    ]
    if available_doctors:
        best = sorted(
            available_doctors,
            key=lambda item: (
                item["distance_km"] if item["distance_km"] is not None else 9999,
                item["role_priority"],
                item["clinic"]["sort_priority"],
            ),
        )[0]
        result = _build_recommendation(best, fallback_used=False)
        result["recommended_date"] = target_date
        return result

    fallback_pool = [c for c in candidates if c["has_availability"]]
    if not fallback_pool:
        fallback_pool = candidates

    best = sorted(
        fallback_pool,
        key=lambda item: (
            item["role_priority"],
            item["distance_km"] if item["distance_km"] is not None else 9999,
            item["clinic"]["sort_priority"],
        ),
    )[0]
    result = _build_recommendation(best, fallback_used=best["clinic"]["role"] != "doctor")
    result["recommended_date"] = target_date
    logger.info(
        "clinic_recommended patient_id=%s clinic_id=%s role=%s fallback=%s",
        patient_id,
        result["clinic_location_id"],
        result["role"],
        result["fallback_used"],
    )
    return result


def format_clinic_recommendation_message(recommendation: dict[str, Any]) -> str:
    times = recommendation.get("available_appointment_times") or []
    times_preview = ", ".join(times[:6])
    if len(times) > 6:
        times_preview += ", ..."

    lines = [
        "Tavsiya etilgan klinika:",
        "",
        f"🏥 {recommendation['clinic_name']}",
        f"👤 {recommendation['staff_name']} ({recommendation['role']})",
        f"📍 {recommendation['address']}",
    ]
    if recommendation.get("phone"):
        lines.append(f"📞 {recommendation['phone']}")
    if recommendation.get("google_maps_link"):
        lines.append(f"🗺 {recommendation['google_maps_link']}")
    if recommendation.get("distance_km") is not None:
        lines.append(f"📏 Masofa: ~{recommendation['distance_km']} km")
    if times_preview:
        lines.append(f"🕐 Bo'sh vaqtlar: {times_preview}")
    if recommendation.get("fallback_used"):
        lines.append("")
        lines.append("ℹ️ Asosiy shifokor band — mavjud talaba/yordamchi tavsiya qilindi.")
    lines.append("")
    lines.append("Qabulga yozilish uchun \"Navbat olmoqchiman\" deb yozing.")
    return "\n".join(lines)
