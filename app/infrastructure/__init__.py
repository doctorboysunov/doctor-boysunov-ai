"""Infrastructure layer — adapters for DB, AI, and external services.

Existing SQLite implementations live in ``app.repositories`` and remain the
runtime source of truth. This package marks the clean-architecture boundary
for future migrations without breaking current handlers.
"""

from app.infrastructure.database import get_connection, init_db

__all__ = ["get_connection", "init_db"]
