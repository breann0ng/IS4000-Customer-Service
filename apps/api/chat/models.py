"""Pydantic schemas for chat session and message API contracts."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """A user message sent to the chatbot for processing."""

    content: str = Field(..., min_length=1, max_length=10000, description="The user's message text")
    file_context: str | None = Field(
        default=None, max_length=50000, description="Extracted text from an uploaded file"
    )
    file_name: str | None = Field(
        default=None, max_length=500, description="Original filename of the uploaded file"
    )
    file_type: str | None = Field(
        default=None, max_length=10, description="File extension (e.g. pdf, png, docx)"
    )
    image_base64: str | None = Field(
        default=None, description="Base64-encoded image data for display in chat"
    )


class FileUploadResponse(BaseModel):
    """Response after a file has been parsed successfully."""

    filename: str
    file_type: str
    extracted_text: str
    is_image: bool
    image_base64: str | None = None


class ChatMessageResponse(BaseModel):
    """A single message within a chat conversation."""

    message_id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    metadata: dict[str, Any] | None = Field(
        default=None, description="Structured metadata for rich UI rendering"
    )
    context: dict | None = None
    created_at: datetime


class ChatSessionCreate(BaseModel):
    """Request body for creating a new chat session."""

    title: str = Field(default="New Chat", max_length=500)


class ChatSessionUpdate(BaseModel):
    """Request body for updating a chat session's metadata."""

    title: str | None = Field(default=None, max_length=500)
    is_archived: bool | None = None


class ChatSessionResponse(BaseModel):
    """Full representation of a chat session with its messages."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = []


class ChatSessionSummary(BaseModel):
    """Lightweight session representation for listing endpoints."""

    session_id: uuid.UUID
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatCompletionResponse(BaseModel):
    """The assistant's response after processing a user message."""

    message: ChatMessageResponse
    agent_trace: dict | None = Field(
        default=None,
        description="Optional trace data from the agentic workflow execution",
    )
