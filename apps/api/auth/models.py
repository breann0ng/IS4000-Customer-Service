"""Pydantic schemas for authentication requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials submitted by the user for LDAP authentication."""

    username: str = Field(..., min_length=1, max_length=255, description="LDAP username")
    password: str = Field(..., min_length=1, description="LDAP password")


class TokenResponse(BaseModel):
    """JWT token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserProfile(BaseModel):
    """Public-facing user profile information."""

    user_id: uuid.UUID
    username: str
    display_name: str
    created_at: datetime
