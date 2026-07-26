"""Application dependency injection container."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.domain.repositories import (
    AppointmentRepository,
    ConversationRepository,
    MemoryRepository,
    UserIdentityRepository,
    UserRepository,
)
from app.infrastructure.database import init_db
from app.infrastructure.repositories.sqlite_adapters import (
    SqliteAppointmentRepository,
    SqliteConversationRepository,
    SqliteMemoryRepository,
    SqliteUserIdentityRepository,
    SqliteUserRepository,
)


@dataclass(frozen=True)
class AppContainer:
    """Wired dependencies for use cases — SQLite implementations by default."""

    users: UserRepository
    identities: UserIdentityRepository
    conversations: ConversationRepository
    appointments: AppointmentRepository
    memories: MemoryRepository


def build_container() -> AppContainer:
    return AppContainer(
        users=SqliteUserRepository(),
        identities=SqliteUserIdentityRepository(),
        conversations=SqliteConversationRepository(),
        appointments=SqliteAppointmentRepository(),
        memories=SqliteMemoryRepository(),
    )


@lru_cache
def get_container() -> AppContainer:
    return build_container()


def bootstrap() -> AppContainer:
    """Initialize infrastructure and return the application container."""
    init_db()
    return get_container()
