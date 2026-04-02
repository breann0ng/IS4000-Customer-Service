"""Chat session and message API routes."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
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
from apps.api.config import settings
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

        logger.info("attempting_title_regeneration", session_id=str(session_id), current_title=session.title)

        new_theme = "UBS Consultation"
        if settings.is_llm_mock_mode:
            query = user_message.lower()
            if any(w in query for w in ["lombard", "loan", "limit", "credit"]):
                new_theme = "Credit Analysis"
            elif any(w in query for w in ["portfolio", "performance", "invest", "allocation"]):
                new_theme = "Portfolio Review"
            elif any(w in query for w in ["cash", "balance", "account", "transfer"]):
                new_theme = "Banking Summary"
            elif any(w in query for w in ["tax", "compliance", "regulatory", "kyc"]):
                new_theme = "Compliance Advisory"
            else:
                new_theme = "Wealth Advisory"
        else:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_model,
                    google_api_key=settings.gemini_api_key,
                    temperature=0.0,
                    max_output_tokens=50,
                )
                prompt = (
                    "You are a professional UBS Wealth Management assistant. "
                    "Generate a highly professional, 2-4 word title for this conversation based on the user's enquiry. "
                    "Examples: 'Portfolio Risk Assessment', 'Market Insights', 'Lending Solutions', 'FX Strategy'. "
                    "If the message is just a greeting, use 'Initial Consultation'. "
                    "Produce only the title, no quotes or punctuation.\n\n"
                    f"User enquiry: {user_message}"
                )
                title_response = await llm.ainvoke([HumanMessage(content=prompt)])
                
                content_val = title_response.content
                if isinstance(content_val, list):
                    content_val = " ".join(
                        [part.get("text", "") if isinstance(part, dict) else str(part) for part in content_val]
                    )
                
                new_theme = str(content_val).strip().replace('"', '')
                if not new_theme or len(new_theme) < 2:
                    new_theme = "UBS Enquiry"
            except Exception as llm_error:
                logger.warning("title_llm_failed_using_default", error=str(llm_error))
                new_theme = "UBS Consultation"

        sg_tz = timezone(timedelta(hours=8))
        current_time_sg = datetime.now(sg_tz).strftime('%d %b %Y, %I:%M %p')
        full_title = f"{new_theme} - {current_time_sg}"

        logger.info("updating_session_title_to_db", session_id=str(session_id), title=full_title)
        
        await update_session(
            database_session,
            session_id,
            user_id,
            title=full_title,
        )
        logger.info("session_title_updated_successfully", session_id=str(session_id), title=full_title)
    except Exception as e:
        logger.exception("failed_to_generate_title_node", error=str(e))


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

    should_attempt_rename = len(session.messages) < 5 or any(m in session.title for m in ["New Chat", "Initial Consultation", "Greeting", "UBS Enquiry"])
    await save_message(database_session, session_id, "user", request.content)

    if check_prompt_injection(request.content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your message was flagged by our security system. Please rephrase your query.",
        )

    sanitized_content = sanitize_input(request.content)

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": sanitized_content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=sanitized_content,
    )

    workflow_result = await run_workflow(
        user_message=sanitized_content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
        username=current_user.username,
    )

    response_text = str(workflow_result["response"])
    # Package structured data for UI rendering
    metadata = {
        "metrics": workflow_result.get("metrics", []),
        "suggestions": workflow_result.get("suggestions", []),
    }

    trace_data = workflow_result.get("trace", {})
    full_context = trace_data or {}
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
        await _generate_and_update_title(database_session, session_id, current_user.user_id, sanitized_content)

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
        agent_trace=trace_data,
    )


def _serialize_for_json(obj: Any) -> Any:
    """Recursively convert UUID, datetime, and Pydantic models to JSON-serializable types."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return _serialize_for_json(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_json(i) for i in obj]
    return obj


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

    should_attempt_rename = len(session.messages) < 5 or any(m in session.title for m in ["New Chat", "Initial Consultation", "Greeting", "UBS Enquiry"])
    await save_message(database_session, session_id, "user", request.content)

    if check_prompt_injection(request.content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your message was flagged by our security system. Please rephrase your query.",
        )

    sanitized_content = sanitize_input(request.content)

    conversation_history = [
        {"role": message.role, "content": message.content} for message in session.messages
    ]
    conversation_history.append({"role": "user", "content": sanitized_content})

    memory_context = await memory_manager.retrieve_memory(
        user_id=str(current_user.user_id),
        query=sanitized_content,
    )

    initial_state = WorkflowState(
        user_message=sanitized_content,
        conversation_history=conversation_history,
        memory_context=memory_context,
        session_id=str(session_id),
        user_id=str(current_user.user_id),
        username=current_user.username,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE events as the workflow graph executes each node."""
        final_response = ""
        trace_data: dict | None = None

        try:
            # Initialize trace data with empty structures
            trace_data = {
                "plan": None,
                "agent_outputs": [],
                "metadata": {
                    "metrics": [],
                    "suggestions": [],
                }
            }

            # Use a manual iterator to support heartbeats (Keep-Alive)
            graph_gen = workflow_graph.astream(initial_state, stream_mode="updates").__aiter__()
            
            while True:
                try:
                    # Wait for next graph event with a 15s timeout for heartbeats
                    event = await asyncio.wait_for(graph_gen.__anext__(), timeout=15.0)
                    
                    for node_name, node_output in event.items():
                        # 1. Handle UI-specific streaming events
                        if node_name == "planner":
                            plan = node_output.get("plan") if isinstance(node_output, dict) else getattr(node_output, "plan", None)
                            if plan:
                                steps = [{"agent": step.agent, "task": step.task} for step in getattr(plan, "steps", [])]
                                yield _sse(
                                    "planning",
                                    {
                                        "reasoning": getattr(plan, "reasoning", ""),
                                        "steps": steps,
                                        "requires_agent": getattr(plan, "requires_agent", True),
                                    },
                                )

                        elif node_name == "executor":
                            outputs = node_output.get("agent_outputs") if isinstance(node_output, dict) else getattr(node_output, "agent_outputs", [])
                            if outputs:
                                latest = outputs[-1]
                                step_index = node_output.get("current_step_index") if isinstance(node_output, dict) else getattr(node_output, "current_step_index", len(outputs))
                                
                                res_val = latest.get("result", "")
                                res_text = getattr(res_val, "response", str(res_val))
                                
                                yield _sse(
                                    "agent_step",
                                    {
                                        "agent": latest.get("agent", "Specialist"),
                                        "result": res_text,
                                        "step_index": step_index,
                                    },
                                )

                        elif node_name == "synthesizer":
                            final_res = node_output.get("final_response") if isinstance(node_output, dict) else getattr(node_output, "final_response", None)
                            if final_res:
                                final_response = final_res
                                trace_data["metadata"]["metrics"] = node_output.get("final_metrics") if isinstance(node_output, dict) else getattr(node_output, "final_metrics", [])
                                trace_data["metadata"]["suggestions"] = node_output.get("final_suggestions") if isinstance(node_output, dict) else getattr(node_output, "final_suggestions", [])
                                yield _sse("synthesizing", {"status": "generating final response"})

                        elif node_name == "escalation":
                            esc_res = node_output.get("final_response") if isinstance(node_output, dict) else getattr(node_output, "final_response", None)
                            if esc_res:
                                final_response = esc_res
                                yield _sse("escalation", {"status": "escalated_to_rm", "response": final_response})

                        elif node_name == "direct_response":
                            dr_res = node_output.get("final_response") if isinstance(node_output, dict) else getattr(node_output, "final_response", None)
                            if dr_res:
                                final_response = dr_res
                                yield _sse("synthesizing", {"status": "generating final response"})

                        # 2. Accumulate full trace data safely
                        if hasattr(node_output, "plan") or (isinstance(node_output, dict) and "plan" in node_output):
                            cur_plan = getattr(node_output, "plan", node_output.get("plan") if isinstance(node_output, dict) else None)
                            if cur_plan:
                                trace_data["plan"] = _serialize_for_json(cur_plan)
                        
                        if hasattr(node_output, "agent_outputs") or (isinstance(node_output, dict) and "agent_outputs" in node_output):
                            cur_outputs = getattr(node_output, "agent_outputs", node_output.get("agent_outputs") if isinstance(node_output, dict) else None)
                            if cur_outputs:
                                trace_data["agent_outputs"] = _serialize_for_json(cur_outputs)

                except asyncio.TimeoutError:
                    # Connection keep-alive heartbeat
                    yield _sse("heartbeat", {"status": "thinking"})
                    continue
                except StopAsyncIteration:
                    break

        except Exception:
            logger.exception("stream_workflow_failed", session_id=str(session_id))
            final_response = (
                "I apologize, but I encountered an error while processing your request. "
                "Please try again or contact your relationship manager."
            )

        if not final_response:
            final_response = "I'm sorry, I couldn't generate a response."

        # Persist the assistant message (sanitize for JSON first)
        trace_data_json = _serialize_for_json(trace_data)
        
        assistant_message = await save_message(
            database_session,
            session_id,
            "assistant",
            final_response,
            context=trace_data_json,
        )

        await memory_manager.store_memory(
            user_id=str(current_user.user_id),
            messages=[
                {"role": "user", "content": request.content},
                {"role": "assistant", "content": final_response},
            ],
        )

        if should_attempt_rename:
            try:
                await _generate_and_update_title(database_session, session_id, current_user.user_id, sanitized_content)
            except Exception:
                logger.error("background_title_update_failed", session_id=str(session_id))

        yield _sse(
            "done",
            {
                "message": {
                    "message_id": str(assistant_message.message_id),
                    "session_id": str(assistant_message.session_id),
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "metadata": trace_data["metadata"],
                    "context": assistant_message.context,
                    "created_at": assistant_message.created_at.isoformat() if assistant_message.created_at else None,
                },
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")



def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event string with safety checks and custom encoding."""
    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "dict"):
                return obj.dict()
            return str(obj) # Final fallback to string representation to avoid TypeError

    try:
        json_data = json.dumps(data, cls=SafeEncoder)
        return f"event: {event}\ndata: {json_data}\n\n"
    except (TypeError, ValueError) as e:
        logger.error("sse_serialization_failed", event=event, error=str(e))
        # Fallback to a safe error event if the payload fails to serialize
        error_payload = json.dumps({"error": "Data serialization failed", "event": event})
        return f"event: error\ndata: {error_payload}\n\n"

