"""Format appointments for admin dashboard messages."""

from typing import Any

ADMIN_ACTION_HELP = (
    "\n\nAdmin actions:\n"
    "/confirm <id>\n"
    "/reschedule <id> YYYY-MM-DD HH:MM\n"
    "/cancel_appt <id>\n"
    "/note <id> your notes"
)


def format_appointment_line(appointment: dict[str, Any]) -> str:
    patient_name = appointment.get("patient_full_name") or appointment.get("telegram_full_name") or "Unknown"
    phone = appointment.get("phone_number") or "-"
    notes = appointment.get("admin_notes") or "-"
    return (
        f"#{appointment['id']} | {appointment['status'].upper()} | "
        f"{appointment['appointment_date']} {appointment['appointment_time']}\n"
        f"Patient: {patient_name} | Tel: {phone}\n"
        f"Doctor: {appointment['doctor_name']} | Complaint: {appointment['complaint']}\n"
        f"Notes: {notes}"
    )


def format_appointment_list(
    appointments: list[dict[str, Any]],
    *,
    title: str,
    include_actions: bool = True,
) -> str:
    if not appointments:
        text = f"{title}\n\nNo appointments found."
    else:
        lines = [title, ""]
        lines.extend(format_appointment_line(item) for item in appointments)
        text = "\n\n".join(lines)

    if include_actions:
        text += ADMIN_ACTION_HELP
    return text
