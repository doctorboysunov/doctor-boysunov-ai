"""Database adapter — re-exports existing connection module."""

from app.db.connection import get_connection, init_db

__all__ = ["get_connection", "init_db"]
