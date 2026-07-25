"""Shared patient profile field definitions."""

PROFILE_FIELDS = (
    "full_name",
    "age",
    "sex",
    "height_cm",
    "weight_kg",
    "phone_number",
    "country",
    "region",
    "district",
    "city_region",
    "address",
    "latitude",
    "longitude",
    "occupation",
    "allergies",
    "chronic_diseases",
    "emergency_contact",
    "email",
    "mobile_push_token",
)

LOCATION_CONTEXT_FIELDS = (
    "country",
    "region",
    "district",
    "address",
    "latitude",
    "longitude",
    "city_region",
)

LIST_MERGE_FIELDS = frozenset({"allergies", "chronic_diseases"})

PROFILE_CONTEXT_FIELDS = tuple(
    field for field in PROFILE_FIELDS if field not in ("email", "mobile_push_token")
)
