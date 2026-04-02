"""Shared customer registry for demo identity-to-profile mapping."""

from __future__ import annotations

USERNAME_TO_CUSTOMER_ID: dict[str, str] = {
    "jsmith": "C-001",
    "ajones": "C-002",
    "mtan": "C-003",
}

DEFAULT_CUSTOMER_ID = "C-001"
ALLOWED_CUSTOMER_IDS: set[str] = set(USERNAME_TO_CUSTOMER_ID.values())


def get_customer_id_for_username(username: str) -> str | None:
    """Return the allowed customer ID for a demo username."""
    return USERNAME_TO_CUSTOMER_ID.get(username.lower())
