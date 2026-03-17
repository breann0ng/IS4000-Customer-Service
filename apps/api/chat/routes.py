"""Chat session and message API routes."""

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.routes import get_current_user
from apps.api.chat.models import (
    ChatCompletionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionSummary,
    ChatSessionUpdate,
)
from apps.api.chat.service import (
    create_session,
    delete_session,
    get_session_with_messages,
    list_sessions,
    save_message,
    update_session,
)
from apps.api.database.connection import get_database_session
from apps.api.database.models import User
from apps.api.logging_config import get_logger
from apps.api.memory.mem0_client import memory_manager
from apps.api.workflow.graph import run_workflow, workflow_graph
from apps.api.workflow.state import WorkflowState

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> ChatSessionResponse:
    """Create a new chat session for the authenticated user.

    Args:
        request: The session creation parameters.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        The newly created chat session.
    """
    session = await create_session(database_session, current_user.user_id, request.title)
    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[],
    )


@router.get("/sessions", response_model=list[ChatSessionSummary])
async def list_chat_sessions(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> list[ChatSessionSummary]:
    """List all chat sessions for the authenticated user.

    Args:
        include_archived: Whether to include archived sessions.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        A list of session summaries with message counts.
    """
    sessions = await list_sessions(database_session, current_user.user_id, include_archived)
    return [ChatSessionSummary(**session_data) for session_data in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> ChatSessionResponse:
    """Retrieve a specific chat session with all messages.

    Args:
        session_id: The ID of the session to retrieve.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        The full chat session with its message history.

    Raises:
        HTTPException: If the session is not found.
    """
    session = await get_session_with_messages(database_session, session_id, current_user.user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                message_id=message.message_id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                context=message.context,
                created_at=message.created_at,
            )
            for message in session.messages
        ],
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: uuid.UUID,
    request: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> ChatSessionResponse:
    """Update a chat session's title or archive status.

    Args:
        session_id: The ID of the session to update.
        request: The fields to update.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        The updated chat session.

    Raises:
        HTTPException: If the session is not found.
    """
    session = await update_session(
        database_session,
        session_id,
        current_user.user_id,
        title=request.title,
        is_archived=request.is_archived,
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        is_archived=session.is_archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                message_id=message.message_id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                context=message.context,
                created_at=message.created_at,
            )
            for message in session.messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> None:
    """Permanently delete a chat session and all its messages.

    Args:
        session_id: The ID of the session to delete.
        current_user: The authenticated user.
        database_session: The async database session.

    Raises:
        HTTPException: If the session is not found.
    """
    deleted = await delete_session(database_session, session_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.post("/sessions/{session_id}/messages", response_model=ChatCompletionResponse)
async def send_message(
    session_id: uuid.UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> ChatCompletionResponse:
    """Send a user message and receive an AI-generated response.

    This endpoint persists the user message, retrieves short-term memory
    from mem0, runs the LangGraph agentic workflow, persists the assistant
    response, and updates mem0 with the new exchange.

    Args:
        session_id: The ID of the session to send the message in.
        request: The user's message content.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        The assistant's response with optional agent trace data.

    Raises:
        HTTPException: If the session is not found.
    """
    session = await get_session_with_messages(database_session, session_id, current_user.user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await save_message(database_session, session_id, "user", request.content)

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": request.content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=request.content,
    )

    workflow_result = await run_workflow(
        user_message=request.content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
    )

    response_text = str(workflow_result["response"])
    trace_data = workflow_result.get("trace")
    trace_dict = trace_data if isinstance(trace_data, dict) else None

    assistant_message = await save_message(
        database_session,
        session_id,
        "assistant",
        response_text,
        context=trace_dict,
    )

    await memory_manager.store_memory(
        user_id=str(current_user.user_id),
        messages=[
            {"role": "user", "content": request.content},
            {"role": "assistant", "content": response_text},
        ],
    )

    return ChatCompletionResponse(
        message=ChatMessageResponse(
            message_id=assistant_message.message_id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            context=assistant_message.context,
            created_at=assistant_message.created_at,
        ),
        agent_trace=trace_dict,
    )


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: uuid.UUID,
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_database_session),
) -> StreamingResponse:
    """Stream a user message response with intermediate thinking steps via SSE.

    Emits events as the workflow progresses through planner, executor (per agent),
    and synthesizer stages, then a final 'done' event with the persisted message.

    Args:
        session_id: The ID of the session to send the message in.
        request: The user's message content.
        current_user: The authenticated user.
        database_session: The async database session.

    Returns:
        A streaming response with text/event-stream content type.

    Raises:
        HTTPException: If the session is not found.
    """
    session = await get_session_with_messages(database_session, session_id, current_user.user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await save_message(database_session, session_id, "user", request.content)

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": request.content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=request.content,
    )

    initial_state = WorkflowState(
        user_message=request.content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE events as the workflow graph executes each node."""
        final_response = ""
        trace_data: dict | None = None

        try:
            async for event in workflow_graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == "planner" and node_output.get("plan"):
                        plan = node_output["plan"]
                        steps = [
                            {"agent": step.agent, "task": step.task}
                            for step in plan.steps
                        ]
                        yield _sse(
                            "planning",
                            {
                                "reasoning": plan.reasoning,
                                "steps": steps,
                                "requires_agent": plan.requires_agent,
                            },
                        )

                    elif node_name == "executor" and node_output.get("agent_outputs"):
                        outputs = node_output["agent_outputs"]
                        if outputs:
                            latest = outputs[-1]
                            step_index = node_output.get(
                                "current_step_index", len(outputs)
                            )
                            yield _sse(
                                "agent_step",
                                {
                                    "agent": latest["agent"],
                                    "result": latest["result"],
                                    "step_index": step_index,
                                },
                            )

                    elif node_name == "synthesizer" and node_output.get("final_response"):
                        final_response = node_output["final_response"]
                        yield _sse("synthesizing", {"status": "generating final response"})

                    elif node_name == "direct_response" and node_output.get("final_response"):
                        final_response = node_output["final_response"]

                    # Build trace from latest state
                    if node_output.get("plan"):
                        plan_obj = node_output["plan"]
                        trace_data = trace_data or {}
                        trace_data["plan"] = plan_obj.model_dump()
                    if node_output.get("agent_outputs"):
                        trace_data = trace_data or {}
                        trace_data["agent_outputs"] = node_output["agent_outputs"]

        except Exception:
            logger.exception("stream_workflow_failed", session_id=str(session_id))
            final_response = (
                "I apologize, but I encountered an error while processing your request. "
                "Please try again or contact your relationship manager."
            )

        if not final_response:
            final_response = "I'm sorry, I couldn't generate a response."

        # Persist the assistant message
        assistant_message = await save_message(
            database_session,
            session_id,
            "assistant",
            final_response,
            context=trace_data,
        )

        await memory_manager.store_memory(
            user_id=str(current_user.user_id),
            messages=[
                {"role": "user", "content": request.content},
                {"role": "assistant", "content": final_response},
            ],
        )

        yield _sse(
            "done",
            {
                "message": {
                    "message_id": str(assistant_message.message_id),
                    "session_id": str(assistant_message.session_id),
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "context": assistant_message.context,
                    "created_at": assistant_message.created_at.isoformat(),
                },
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event string.

    Args:
        event: The event type name.
        data: The JSON-serializable payload.

    Returns:
        A properly formatted SSE string.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
