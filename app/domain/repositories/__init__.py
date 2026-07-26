"""Repository interfaces — domain contracts implemented in infrastructure."""

from app.domain.repositories.appointment_repository import AppointmentRepository
from app.domain.repositories.conversation_repository import ConversationRepository
from app.domain.repositories.memory_repository import MemoryRepository
from app.domain.repositories.user_identity_repository import UserIdentityRepository
from app.domain.repositories.user_repository import UserRepository

__all__ = [
    "AppointmentRepository",
    "ConversationRepository",
    "MemoryRepository",
    "UserIdentityRepository",
    "UserRepository",
]
