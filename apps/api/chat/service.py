"""Business logic for chat session and message management."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database.models import ChatMessage, ChatSession
from apps.api.logging_config import get_logger

logger = get_logger(__name__)


async def create_session(
    database_session: AsyncSession,
    user_id: uuid.UUID,
    title: str = "New Chat",
) -> ChatSession:
    """Create a new chat session for the given user.

    Args:
        database_session: The async database session.
        user_id: The ID of the user who owns the session.
        title: The display title for the session.

    Returns:
        The newly created ChatSession instance.
    """
    session = ChatSession(user_id=user_id, title=title)
    database_session.add(session)
    await database_session.commit()
    await database_session.refresh(session)
    logger.info("chat_session_created", session_id=str(session.session_id), user_id=str(user_id))
    return session


async def list_sessions(
    database_session: AsyncSession,
    user_id: uuid.UUID,
    include_archived: bool = False,
) -> list[dict]:
    """Retrieve all chat sessions for a user with message counts.

    Args:
        database_session: The async database session.
        user_id: The ID of the user whose sessions to list.
        include_archived: Whether to include archived sessions.

    Returns:
        A list of session dictionaries with message counts.
    """
    message_count_subquery = (
        select(
            ChatMessage.session_id,
            func.count(ChatMessage.message_id).label("message_count"),
        )
        .group_by(ChatMessage.session_id)
        .subquery()
    )

    query = (
        select(ChatSession, message_count_subquery.c.message_count)
        .outerjoin(
            message_count_subquery,
            ChatSession.session_id == message_count_subquery.c.session_id,
        )
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )

    if not include_archived:
        query = query.where(ChatSession.is_archived == False)  # noqa: E712

    result = await database_session.execute(query)
    rows = result.all()

    return [
        {
            "session_id": row.ChatSession.session_id,
            "title": row.ChatSession.title,
            "is_archived": row.ChatSession.is_archived,
            "created_at": row.ChatSession.created_at,
            "updated_at": row.ChatSession.updated_at,
            "message_count": row.message_count or 0,
        }
        for row in rows
    ]


async def get_session_with_messages(
    database_session: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatSession | None:
    """Fetch a chat session with all its messages.

    Args:
        database_session: The async database session.
        session_id: The ID of the session to retrieve.
        user_id: The ID of the requesting user for ownership validation.

    Returns:
        The ChatSession with eagerly loaded messages, or None if not found.
    """
    result = await database_session.execute(
        select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_session(
    database_session: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str | None = None,
    is_archived: bool | None = None,
) -> ChatSession | None:
    """Update a chat session's title or archive status.

    Args:
        database_session: The async database session.
        session_id: The ID of the session to update.
        user_id: The ID of the requesting user for ownership validation.
        title: The new title, if changing.
        is_archived: The new archive status, if changing.

    Returns:
        The updated ChatSession, or None if not found.
    """
    session = await get_session_with_messages(database_session, session_id, user_id)
    if session is None:
        return None

    if title is not None:
        session.title = title
    if is_archived is not None:
        session.is_archived = is_archived

    await database_session.commit()
    await database_session.refresh(session)
    logger.info("chat_session_updated", session_id=str(session_id))
    return session


async def delete_session(
    database_session: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Permanently delete a chat session and all its messages.

    Args:
        database_session: The async database session.
        session_id: The ID of the session to delete.
        user_id: The ID of the requesting user for ownership validation.

    Returns:
        True if the session was deleted, False if not found.
    """
    session = await get_session_with_messages(database_session, session_id, user_id)
    if session is None:
        return False

    await database_session.delete(session)
    await database_session.commit()
    logger.info("chat_session_deleted", session_id=str(session_id))
    return True


async def save_message(
    database_session: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    context: dict | None = None,
) -> ChatMessage:
    """Persist a new message in the given chat session.

    Args:
        database_session: The async database session.
        session_id: The ID of the session this message belongs to.
        role: The message role (e.g. 'user', 'assistant').
        content: The text content of the message.
        context: Optional JSONB metadata (tool calls, traces, etc.).

    Returns:
        The newly created ChatMessage instance.
    """
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        context=context,
    )
    database_session.add(message)
    await database_session.commit()
    await database_session.refresh(message)
    return message
