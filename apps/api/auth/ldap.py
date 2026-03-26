"""Mock LDAP authentication service.

This module simulates LDAP directory lookups for local development.
Replace the mock implementation with a real LDAP client (e.g. python-ldap)
when deploying against a corporate directory.
"""

from apps.api.logging_config import get_logger

logger = get_logger(__name__)

MOCK_LDAP_DIRECTORY: dict[str, dict[str, str]] = {
    "jsmith": {"password": "password123", "display_name": "John Smith"},
    "ajones": {"password": "password123", "display_name": "Alice Jones"},
    "bwilson": {"password": "password123", "display_name": "Bob Wilson"},
}


async def authenticate_ldap_user(username: str, password: str) -> dict[str, str] | None:
    """Validate credentials against the mock LDAP directory.

    Args:
        username: The LDAP username to authenticate.
        password: The plaintext password to verify.

    Returns:
        A dictionary with user attributes if authentication succeeds,
        or None if the credentials are invalid.
    """
    logger.info("ldap_authentication_attempt", username=username)

    user_entry = MOCK_LDAP_DIRECTORY.get(username)
    if user_entry is None:
        logger.warning("ldap_user_not_found", username=username)
        return None

    if user_entry["password"] != password:
        logger.warning("ldap_invalid_password", username=username)
        return None

    logger.info("ldap_authentication_success", username=username)
    return {"username": username, "display_name": user_entry["display_name"]}
