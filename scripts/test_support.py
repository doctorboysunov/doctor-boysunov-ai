"""Shared helpers for verification scripts."""

from app.repositories.patient_profile_repository import update_patient_profile


def seed_default_location(user_id: int) -> None:
    update_patient_profile(
        user_id,
        country="O'zbekiston",
        region="Toshkent",
        district="Yunusobod",
        city_region="Toshkent",
    )
