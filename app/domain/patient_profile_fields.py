"""Shared patient profile field definitions."""

PROFILE_FIELDS = (
    "full_name",
    "age",
    "sex",
    "height_cm",
    "weight_kg",
    "phone_number",
    "city_region",
    "address",
    "occupation",
    "allergies",
    "chronic_diseases",
    "emergency_contact",
)

LIST_MERGE_FIELDS = frozenset({"allergies", "chronic_diseases"})

PROFILE_CONTEXT_FIELDS = PROFILE_FIELDS
