"""Authentication API routes for login and user profile retrieval."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.ldap import authenticate_ldap_user
from apps.api.auth.models import LoginRequest, TokenResponse, UserProfile
from apps.api.config import settings
from apps.api.database.connection import get_database_session
from apps.api.database.models import User
from apps.api.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
security_scheme = HTTPBearer()


def create_access_token(user_id: str) -> tuple[str, int]:
    """Generate a signed JWT access token for the given user.

    Args:
        user_id: The unique identifier of the authenticated user.

    Returns:
        A tuple of the encoded JWT string and its expiration time in seconds.
    """
    expires_delta = timedelta(minutes=settings.jwt_expiration_minutes)
    expire = datetime.now(UTC) + expires_delta
    payload = {"sub": user_id, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    database_session: AsyncSession = Depends(get_database_session),
) -> User:
    """Extract and validate the current user from the Authorization header.

    Args:
        credentials: The Bearer token extracted by the security scheme.
        database_session: The async database session.

    Returns:
        The authenticated User ORM instance.

    Raises:
        HTTPException: If the token is invalid or the user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError as error:
        raise credentials_exception from error

    result = await database_session.execute(
        select(User).where(User.user_id == uuid.UUID(user_id_str))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    database_session: AsyncSession = Depends(get_database_session),
) -> TokenResponse:
    """Authenticate a user via LDAP and return a JWT token.

    Args:
        request: The login credentials.
        database_session: The async database session.

    Returns:
        A JWT token response on successful authentication.

    Raises:
        HTTPException: If LDAP authentication fails.
    """
    ldap_result = await authenticate_ldap_user(request.username, request.password)
    if ldap_result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    result = await database_session.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username=ldap_result["username"],
            display_name=ldap_result["display_name"],
        )
        database_session.add(user)
        await database_session.commit()
        await database_session.refresh(user)
        logger.info("user_created", user_id=str(user.user_id), username=user.username)

    token, expires_in = create_access_token(str(user.user_id))
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)) -> UserProfile:
    """Return the profile of the currently authenticated user.

    Args:
        current_user: The authenticated user from the JWT token.

    Returns:
        The user's public profile information.
    """
    return UserProfile(
        user_id=current_user.user_id,
        username=current_user.username,
        display_name=current_user.display_name,
        created_at=current_user.created_at,
    )
