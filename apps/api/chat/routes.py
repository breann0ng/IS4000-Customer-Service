"""Chat session and message API routes."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.routes import get_current_user
from apps.api.chat.file_parser import parse_file, validate_upload
from apps.api.chat.models import (
    ChatCompletionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionSummary,
    ChatSessionUpdate,
    FileUploadResponse,
)
from apps.api.chat.service import (
    create_session,
    delete_session,
    get_session_with_messages,
    list_sessions,
    save_message,
    update_session,
)
from apps.api.config import settings
from apps.api.customers.registry import DEFAULT_CUSTOMER_ID
from apps.api.database.connection import get_database_session
from apps.api.database.models import User
from apps.api.logging_config import get_logger
from apps.api.memory.mem0_client import memory_manager
from apps.api.security.input_guard import check_prompt_injection, sanitize_input
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
                metadata=message.context.get("metadata") if message.context else None,
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
                metadata=message.context.get("metadata") if message.context else None,
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


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> FileUploadResponse:
    """Upload and parse a file for use in chat messages.

    Supports PDF, DOCX, Excel (xlsx/xls), and image files (png, jpg, jpeg, gif, webp).
    Returns extracted text content that can be sent with a chat message.

    Args:
        file: The uploaded file.
        current_user: The authenticated user.

    Returns:
        The parsed file content and metadata.
    """
    is_valid, error_msg = await validate_upload(file)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    result = await parse_file(file)
    return FileUploadResponse(**result)


def _build_augmented_message(content: str, file_context: str | None, file_name: str | None) -> str:
    """Prepend file context to the user message if a file was attached."""
    if not file_context:
        return content
    label = f"[Attached file: {file_name}]" if file_name else "[Attached file]"
    return f"{label}\n\n{file_context}\n\n---\n\nUser question: {content}"


def _build_user_message_context(request: ChatMessageRequest) -> dict | None:
    """Build context dict for a user message with optional file attachment metadata."""
    if not request.file_name:
        return None
    ctx: dict = {
        "attached_file": request.file_name,
        "file_type": request.file_type,
    }
    if request.image_base64:
        ctx["image_base64"] = request.image_base64
    return ctx


async def _generate_and_update_title(
    database_session: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    user_message: str,
) -> None:
    """Generate a high-quality professional title from the message and update the session."""
    try:
        session = await get_session_with_messages(database_session, session_id, user_id)
        if not session:
            logger.error("rename_session_not_found", session_id=str(session_id))
            return

        # Only rename if generic or a temporary greeting title
        generic_markers = [
            "New Chat",
            "Account Performance Q&A",
            "Initial Consultation",
            "Greeting",
            "UBS Enquiry",
        ]
        is_generic = any(marker in session.title for marker in generic_markers)

        if not is_generic:
            return

        new_theme = "UBS Enquiry"
        if settings.is_llm_mock_mode:
            new_theme = "Mock Analysis"
        else:
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=0.0,
                max_output_tokens=50,
            )
            prompt = (
                "You are a professional UBS Wealth Management assistant. "
                "Generate a highly professional, 2-4 word title for this conversation "
                "based on the user's enquiry. "
                "Examples: 'Portfolio Risk Assessment', 'Market Insights', "
                "'Lending Solutions', 'FX Strategy'. "
                "If the message is just a greeting, use 'Initial Consultation'. "
                "Produce only the title, no quotes or punctuation.\n\n"
                f"User enquiry: {user_message}"
            )
            title_response = await llm.ainvoke([HumanMessage(content=prompt)])

            content_val = title_response.content
            if isinstance(content_val, list):
                content_val = " ".join(
                    [
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content_val
                    ]
                )

            new_theme = str(content_val).strip().replace('"', "")

        sg_tz = timezone(timedelta(hours=8))
        # Format: 29 Mar 2026, 05:51 PM
        current_time_sg = datetime.now(sg_tz).strftime("%d %b %Y, %I:%M %p")
        full_title = f"{new_theme} - {current_time_sg}"

        logger.info("updating_session_title", session_id=str(session_id), title=full_title)

        updated_session = await update_session(
            database_session,
            session_id,
            user_id,
            title=full_title,
        )
        if updated_session:
            logger.info(
                "session_title_updated_successfully", session_id=str(session_id), title=full_title
            )
    except Exception as e:
        logger.exception("failed_to_generate_title", error=str(e))


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

    should_attempt_rename = len(session.messages) < 5 or any(
        m in session.title for m in ["New Chat", "Initial Consultation", "Greeting", "UBS Enquiry"]
    )

    # Build user message context with file metadata for display
    user_msg_context = _build_user_message_context(request)
    await save_message(
        database_session, session_id, "user", request.content, context=user_msg_context
    )

    if check_prompt_injection(request.content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your message was flagged by our security system. Please rephrase your query.",
        )

    sanitized_content = sanitize_input(request.content)
    augmented_message = _build_augmented_message(
        sanitized_content, request.file_context, request.file_name
    )

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": sanitized_content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=sanitized_content,
    )

    workflow_result = await run_workflow(
        user_message=augmented_message,
        escalation_text=sanitized_content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
        customer_id=str(current_user.customer_id)
        if current_user.customer_id
        else DEFAULT_CUSTOMER_ID,
    )

    response_text = str(workflow_result["response"])
    # Package structured data for UI rendering
    metadata = {
        "metrics": workflow_result.get("metrics", []),
        "suggestions": workflow_result.get("suggestions", []),
    }

    trace_val = workflow_result.get("trace")
    full_context: dict = trace_val if isinstance(trace_val, dict) else {}
    full_context["metadata"] = metadata

    assistant_message = await save_message(
        database_session,
        session_id,
        "assistant",
        response_text,
        context=full_context,
    )

    await memory_manager.store_memory(
        user_id=str(current_user.user_id),
        messages=[
            {"role": "user", "content": request.content},
            {"role": "assistant", "content": response_text},
        ],
    )

    if should_attempt_rename:
        await _generate_and_update_title(
            database_session, session_id, current_user.user_id, sanitized_content
        )

    return ChatCompletionResponse(
        message=ChatMessageResponse(
            message_id=assistant_message.message_id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            metadata=metadata,
            context=assistant_message.context,
            created_at=assistant_message.created_at,
        ),
        agent_trace=full_context,
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

    should_attempt_rename = len(session.messages) < 5 or any(
        m in session.title for m in ["New Chat", "Initial Consultation", "Greeting", "UBS Enquiry"]
    )

    user_msg_context = _build_user_message_context(request)
    await save_message(
        database_session, session_id, "user", request.content, context=user_msg_context
    )

    if check_prompt_injection(request.content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your message was flagged by our security system. Please rephrase your query.",
        )

    sanitized_content = sanitize_input(request.content)
    augmented_message = _build_augmented_message(
        sanitized_content, request.file_context, request.file_name
    )

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": sanitized_content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=sanitized_content,
    )

    initial_state = WorkflowState(
        user_message=augmented_message,
        escalation_text=sanitized_content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
        customer_id=str(current_user.customer_id)
        if current_user.customer_id
        else DEFAULT_CUSTOMER_ID,
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
                        steps = [{"agent": step.agent, "task": step.task} for step in plan.steps]
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
                            step_index = node_output.get("current_step_index", len(outputs))
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
                        # Store structural metadata from sanitizer output
                        trace_data = trace_data or {}
                        trace_data["metadata"] = {
                            "metrics": node_output.get("final_metrics", []),
                            "suggestions": node_output.get("final_suggestions", []),
                        }
                        yield _sse("synthesizing", {"status": "generating final response"})

                    elif node_name == "escalation" and node_output.get("final_response"):
                        final_response = node_output["final_response"]
                        yield _sse(
                            "escalation",
                            {
                                "status": "escalated_to_rm",
                                "response": final_response,
                            },
                        )

                    elif node_name == "direct_response" and node_output.get("final_response"):
                        final_response = node_output["final_response"]
                        yield _sse("synthesizing", {"status": "generating final response"})

                    # Build trace from latest state
                    if isinstance(node_output, dict):
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

        if should_attempt_rename:
            await _generate_and_update_title(
                database_session, session_id, current_user.user_id, sanitized_content
            )

        yield _sse(
            "done",
            {
                "message": {
                    "message_id": str(assistant_message.message_id),
                    "session_id": str(assistant_message.session_id),
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "metadata": trace_data.get("metadata") if trace_data else None,
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
