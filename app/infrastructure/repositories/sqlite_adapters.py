"""SQLite repository adapters — implement domain protocols via existing modules."""

from __future__ import annotations

from typing import Any

from app.domain.channels import ChannelType, DEFAULT_CHANNEL
from app.domain.entities.appointment import Appointment
from app.domain.entities.message import Message
from app.domain.entities.patient_memory import PatientMemory
from app.domain.entities.user import User
from app.repositories import appointment_repository as appointment_repo
from app.repositories import conversation_repository as conversation_repo
from app.repositories import memory_repository as memory_repo
from app.repositories import user_identity_repository as identity_repo
from app.db.connection import get_connection


class SqliteUserRepository:
    def upsert_telegram_user(
        self,
        telegram_id: int,
        *,
        username: str | None = None,
        full_name: str | None = None,
    ) -> int:
        return conversation_repo.upsert_user(
            telegram_id,
            username=username,
            full_name=full_name,
        )

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, telegram_id, username, full_name, registration_source, created_at
                FROM users WHERE telegram_id = ?
                """,
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None
        return User(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]) if row["telegram_id"] is not None else None,
            username=row["username"],
            full_name=row["full_name"],
            registration_source=row["registration_source"] or "telegram",
            created_at=row["created_at"] or "",
        )


class SqliteUserIdentityRepository:
    def resolve_user_id(self, channel: ChannelType, external_id: str) -> int | None:
        return identity_repo.resolve_user_id(channel, external_id)

    def upsert_channel_identity(
        self,
        channel: ChannelType,
        external_id: str,
        *,
        user_id: int | None = None,
        display_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return identity_repo.upsert_channel_identity(
            channel,
            external_id,
            user_id=user_id,
            display_name=display_name,
            metadata=metadata,
        )

    def list_user_channels(self, user_id: int) -> list[dict[str, Any]]:
        return identity_repo.list_user_channels(user_id)


class SqliteConversationRepository:
    def get_or_create_active_conversation(
        self,
        user_id: int,
        *,
        channel: ChannelType = DEFAULT_CHANNEL,
        external_thread_id: str | None = None,
    ) -> int:
        return conversation_repo.get_or_create_active_conversation(
            user_id,
            channel=channel,
            external_thread_id=external_thread_id,
        )

    def save_message(self, conversation_id: int, role: str, content: str) -> None:
        conversation_repo.save_message(conversation_id, role, content)

    def get_last_messages(self, conversation_id: int, limit: int = 10) -> list[Message]:
        rows = conversation_repo.get_last_messages(conversation_id, limit=limit)
        return [
            Message(
                id=index + 1,
                conversation_id=conversation_id,
                role=row["role"],  # type: ignore[arg-type]
                content=row["content"],
            )
            for index, row in enumerate(rows)
        ]

    def set_last_response_id(self, conversation_id: int, response_id: str) -> None:
        conversation_repo.set_last_response_id(conversation_id, response_id)

    def get_last_response_id(self, conversation_id: int) -> str | None:
        return conversation_repo.get_last_response_id(conversation_id)

    def close_conversation(self, conversation_id: int, *, summary: str | None = None) -> None:
        conversation_repo.close_conversation(conversation_id, summary=summary)

    def set_conversation_summary(self, conversation_id: int, summary: str) -> None:
        conversation_repo.set_conversation_summary(conversation_id, summary)

    def get_prior_conversation_summaries(
        self,
        user_id: int,
        *,
        exclude_conversation_id: int | None = None,
        limit: int = 5,
    ) -> list[str]:
        return conversation_repo.get_prior_conversation_summaries(
            user_id,
            exclude_conversation_id=exclude_conversation_id,
            limit=limit,
        )


class SqliteAppointmentRepository:
    def create_appointment(
        self,
        *,
        patient_id: int,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        complaint: str,
        status: str = "pending",
    ) -> int:
        row = appointment_repo.create_appointment(
            patient_id=patient_id,
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            complaint=complaint,
            status=status,
        )
        return int(row["id"])

    def get_patient_appointments(self, patient_id: int) -> list[Appointment]:
        rows = appointment_repo.get_patient_appointments(patient_id)
        return [
            Appointment(
                id=int(row["id"]),
                patient_id=int(row["patient_id"]),
                doctor_name=str(row["doctor_name"] or ""),
                appointment_date=str(row["appointment_date"] or ""),
                appointment_time=str(row["appointment_time"] or ""),
                complaint=str(row["complaint"] or ""),
                status=str(row["status"] or "pending"),
                created_at=str(row.get("created_at") or ""),
            )
            for row in rows
        ]

    def update_status(self, appointment_id: int, status: str) -> None:
        appointment_repo.update_status(appointment_id, status)

    def cancel_appointment(self, appointment_id: int) -> None:
        appointment_repo.cancel_appointment(appointment_id)


class SqliteMemoryRepository:
    """Persistent long-term memory backed by patient_memories table."""

    def upsert_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        *,
        source_message_id: int | None = None,
        confidence: float | None = None,
    ) -> None:
        memory_repo.upsert_memory(
            user_id,
            key,
            value,
            source_message_id=source_message_id,
            confidence=confidence,
        )

    def get_memories(self, user_id: int) -> list[PatientMemory]:
        return [
            PatientMemory(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                key=row["key"],
                value=row["value"],
                source_message_id=row["source_message_id"],
                confidence=row["confidence"],
                updated_at=str(row["updated_at"] or ""),
            )
            for row in memory_repo.get_memories(user_id)
        ]

    def delete_memory(self, user_id: int, key: str) -> None:
        memory_repo.delete_memory(user_id, key)
