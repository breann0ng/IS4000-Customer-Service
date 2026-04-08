"""Helpers for gathering RM escalation details across multiple chat turns."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.escalation import check_escalation

logger = get_logger(__name__)

MEETING_FORMAT_ONLINE = "online"
MEETING_FORMAT_IN_PERSON = "in-person"

_TIME_KEYWORDS = (
    "today",
    "tomorrow",
    "tonight",
    "morning",
    "afternoon",
    "evening",
    "next week",
    "next monday",
    "next tuesday",
    "next wednesday",
    "next thursday",
    "next friday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "am",
    "pm",
)


class RMIntakeAnswers(BaseModel):
    """Structured answers required for RM escalation handoff."""

    preferred_contact_time: str | None = None
    meeting_format: Literal["online", "in-person"] | None = None
    agenda: str | None = None
    top_outcomes: list[str] = Field(default_factory=list)


class RMIntakeState(BaseModel):
    """State persisted in assistant message context while gathering RM details."""

    kind: Literal["rm_intake"] = "rm_intake"
    status: Literal["collecting", "completed"] = "collecting"
    trigger_message: str
    started_at: str
    last_updated_at: str
    collected_answers: RMIntakeAnswers = Field(default_factory=RMIntakeAnswers)
    missing_fields: list[str] = Field(default_factory=list)
    summary: str | None = None


class RMIntakeExtraction(BaseModel):
    """Structured extraction for a user's follow-up answers."""

    preferred_contact_time: str | None = None
    meeting_format: Literal["online", "in-person"] | None = None
    agenda: str | None = None
    top_outcomes: list[str] = Field(default_factory=list)


class RMIntakeSummary(BaseModel):
    """Short RM-ready prep summary."""

    summary: str = Field(description="Short summary for the RM, 2-4 sentences max.")


class RMIntakeTurnResult(BaseModel):
    """Response payload returned to the chat route."""

    response: str
    metadata: dict[str, Any] = Field(default_factory=lambda: _build_metadata())
    context: dict[str, Any]


def get_active_rm_intake(session_messages: Sequence[Any]) -> RMIntakeState | None:
    """Return the most recent active RM intake state from session messages."""
    for message in reversed(session_messages):
        if getattr(message, "role", None) != "assistant":
            continue
        context = getattr(message, "context", None) or {}
        raw_state = context.get("rm_intake")
        if not raw_state:
            continue
        try:
            intake_state = RMIntakeState.model_validate(raw_state)
        except Exception:
            logger.exception("rm_intake_state_invalid")
            return None
        if intake_state.status == "collecting":
            return intake_state
        return None
    return None


async def maybe_handle_rm_intake(
    *,
    session_messages: Sequence[Any],
    current_user_message: str,
    conversation_history: list[dict[str, str]],
) -> RMIntakeTurnResult | None:
    """Intercept escalation turns and run the RM intake flow when needed."""
    active_state = get_active_rm_intake(session_messages)
    if active_state is None and not check_escalation(current_user_message):
        return None

    if active_state is None:
        return _start_rm_intake(current_user_message)

    return await _continue_rm_intake(
        state=active_state,
        current_user_message=current_user_message,
        conversation_history=conversation_history,
    )


def _start_rm_intake(trigger_message: str) -> RMIntakeTurnResult:
    """Start a new RM intake and ask the required follow-up questions."""
    timestamp = _utc_now()
    state = RMIntakeState(
        trigger_message=trigger_message,
        started_at=timestamp,
        last_updated_at=timestamp,
        missing_fields=_get_missing_fields(RMIntakeAnswers()),
    )
    response = (
        "This is best handled by your Relationship Manager. Before I hand this over, "
        "please help me with these four quick details so your RM can prepare well:\n\n"
        "1. When would you like your RM to contact you?\n"
        "2. Would you prefer an online or in-person meeting?\n"
        "3. What agenda should your RM prepare for?\n"
        "4. What are the top 3 things you want to get out of the meeting?\n\n"
        "You can reply in one message using bullets or numbering."
    )
    return RMIntakeTurnResult(
        response=response,
        context={
            "metadata": _build_metadata(),
            "rm_intake": state.model_dump(),
        },
    )


async def _continue_rm_intake(
    *,
    state: RMIntakeState,
    current_user_message: str,
    conversation_history: list[dict[str, str]],
) -> RMIntakeTurnResult:
    """Merge the user's latest reply into the RM intake and continue or complete it."""
    extracted = await _extract_answers(
        current_user_message=current_user_message,
        conversation_history=conversation_history,
        existing_answers=state.collected_answers,
    )
    merged_answers = _merge_answers(state.collected_answers, extracted)
    missing_fields = _get_missing_fields(merged_answers)
    updated_state = RMIntakeState(
        trigger_message=state.trigger_message,
        started_at=state.started_at,
        last_updated_at=_utc_now(),
        collected_answers=merged_answers,
        missing_fields=missing_fields,
        summary=state.summary,
        status="collecting",
    )

    if missing_fields:
        response = _build_missing_details_response(merged_answers, missing_fields)
        return RMIntakeTurnResult(
            response=response,
            context={
                "metadata": _build_metadata(),
                "rm_intake": updated_state.model_dump(),
            },
        )

    summary = await _build_rm_summary(
        trigger_message=state.trigger_message,
        answers=merged_answers,
        conversation_history=conversation_history,
    )
    completed_state = updated_state.model_copy(
        update={
            "status": "completed",
            "summary": summary,
            "missing_fields": [],
        }
    )
    response = (
        "Thank you. I’ve gathered the details your Relationship Manager needs.\n\n"
        "### RM Handoff Summary\n"
        f"{summary}"
    )
    return RMIntakeTurnResult(
        response=response,
        context={
            "metadata": _build_metadata(),
            "rm_intake": completed_state.model_dump(),
        },
    )


async def _extract_answers(
    *,
    current_user_message: str,
    conversation_history: list[dict[str, str]],
    existing_answers: RMIntakeAnswers,
) -> RMIntakeExtraction:
    """Extract RM intake answers from the user's latest reply."""
    if settings.is_llm_mock_mode:
        return _fallback_extract_answers(current_user_message)

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.0,
            max_output_tokens=400,
        ).with_structured_output(RMIntakeExtraction)

        recent_history = _format_recent_conversation(conversation_history)
        prompt = (
            "Extract only the information needed for an RM meeting handoff. "
            "Use recent conversation context when the user says things like "
            "'same as above' or 'as discussed'. "
            "Normalize meeting_format to 'online' or 'in-person'. "
            "Return at most 3 top_outcomes and keep each one concise. "
            "If a field is still missing, leave it empty.\n\n"
            f"Existing answers: {existing_answers.model_dump_json()}\n\n"
            f"Recent conversation:\n{recent_history}\n\n"
            f"Latest user reply:\n{current_user_message}"
        )
        return await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You extract structured meeting intake details for a private banking "
                        "RM handoff. Do not invent information."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
    except Exception:
        logger.exception("rm_intake_extraction_failed")
        return _fallback_extract_answers(current_user_message)


async def _build_rm_summary(
    *,
    trigger_message: str,
    answers: RMIntakeAnswers,
    conversation_history: list[dict[str, str]],
) -> str:
    """Build a concise RM-facing summary from chat context and collected answers."""
    if settings.is_llm_mock_mode:
        return _fallback_build_summary(trigger_message, answers, conversation_history)

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.2,
            max_output_tokens=300,
        ).with_structured_output(RMIntakeSummary)

        prompt = (
            "Create a short RM preparation summary using both the recent chat context "
            "and the confirmed intake answers. Keep it to 2-4 sentences. "
            "Include the client's preferred timing, meeting format, agenda, "
            "and top desired outcomes. Mention only relevant context from the chat.\n\n"
            f"Original escalation request: {trigger_message}\n\n"
            f"Confirmed intake answers: {answers.model_dump_json()}\n\n"
            f"Recent conversation:\n{_format_recent_conversation(conversation_history)}"
        )
        result = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You write concise internal prep notes for a relationship manager. "
                        "Be specific, factual, and brief."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
        return result.summary.strip()
    except Exception:
        logger.exception("rm_intake_summary_failed")
        return _fallback_build_summary(trigger_message, answers, conversation_history)


def _fallback_extract_answers(user_message: str) -> RMIntakeExtraction:
    """Extract answers using lightweight heuristics when LLM parsing is unavailable."""
    sections = _extract_numbered_sections(user_message)
    preferred_contact_time = _extract_preferred_time(user_message, sections.get(1))
    meeting_format = _extract_meeting_format(user_message, sections.get(2))
    agenda = _extract_agenda(user_message, sections.get(3))
    top_outcomes = _extract_top_outcomes(user_message, sections.get(4))

    if agenda is None:
        agenda = _extract_agenda(user_message, None)
    if not top_outcomes:
        top_outcomes = _extract_top_outcomes(user_message, None)

    return RMIntakeExtraction(
        preferred_contact_time=preferred_contact_time,
        meeting_format=meeting_format,
        agenda=agenda,
        top_outcomes=top_outcomes,
    )


def _fallback_build_summary(
    trigger_message: str,
    answers: RMIntakeAnswers,
    conversation_history: list[dict[str, str]],
) -> str:
    """Create a deterministic RM summary when LLM summarization is unavailable."""
    recent_context = _collect_recent_user_context(conversation_history, trigger_message)
    outcomes = ", ".join(answers.top_outcomes[:3])
    context_line = f" Recent context from the chat: {recent_context}." if recent_context else ""
    return (
        f"Client requested RM follow-up regarding {answers.agenda or trigger_message}. "
        f"Preferred contact timing is {answers.preferred_contact_time or 'to be confirmed'}, "
        f"with a {answers.meeting_format or 'preferred'} meeting format. "
        f"The client wants to achieve: {outcomes or 'their main priorities were not captured'}."
        f"{context_line}"
    )


def _merge_answers(existing: RMIntakeAnswers, new: RMIntakeExtraction) -> RMIntakeAnswers:
    """Merge newly extracted answers into the persisted intake answers."""
    top_outcomes = existing.top_outcomes.copy()
    for outcome in new.top_outcomes:
        normalized = _clean_text(outcome)
        if normalized and normalized not in top_outcomes:
            top_outcomes.append(normalized)

    return RMIntakeAnswers(
        preferred_contact_time=new.preferred_contact_time or existing.preferred_contact_time,
        meeting_format=new.meeting_format or existing.meeting_format,
        agenda=new.agenda or existing.agenda,
        top_outcomes=top_outcomes[:3],
    )


def _get_missing_fields(answers: RMIntakeAnswers) -> list[str]:
    """Return the required intake fields that still need answers."""
    missing_fields: list[str] = []
    if not answers.preferred_contact_time:
        missing_fields.append("preferred_contact_time")
    if not answers.meeting_format:
        missing_fields.append("meeting_format")
    if not answers.agenda:
        missing_fields.append("agenda")
    if len(answers.top_outcomes) < 3:
        missing_fields.append("top_outcomes")
    return missing_fields


def _build_missing_details_response(answers: RMIntakeAnswers, missing_fields: list[str]) -> str:
    """Ask only for the remaining RM intake details that are still missing."""
    questions: list[str] = []
    for field_name in missing_fields:
        if field_name == "preferred_contact_time":
            questions.append("When would you like your RM to contact you?")
        elif field_name == "meeting_format":
            questions.append("Would you prefer an online or in-person meeting?")
        elif field_name == "agenda":
            questions.append("What agenda should your RM prepare for?")
        elif field_name == "top_outcomes":
            remaining = max(3 - len(answers.top_outcomes), 1)
            if remaining == 3:
                questions.append("What are the top 3 things you want to get out of the meeting?")
            elif remaining == 1:
                questions.append("What is the last key outcome you want to get out of the meeting?")
            else:
                questions.append(
                    f"What are the remaining {remaining} things you want to get out of the meeting?"
                )

    numbered_questions = "\n".join(
        f"{index}. {question}" for index, question in enumerate(questions, start=1)
    )
    return (
        "Thanks, I’ve captured part of the handoff. I still need:\n\n"
        f"{numbered_questions}\n\n"
        "You can reply in one message."
    )


def _extract_numbered_sections(user_message: str) -> dict[int, str]:
    """Split a numbered reply into sections keyed by question number."""
    sections: dict[int, list[str]] = {}
    current_section: int | None = None

    for raw_line in user_message.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(r"^([1-4])(?:[.):]|\s)\s*(.*)$", line)
        if match:
            current_section = int(match.group(1))
            sections.setdefault(current_section, [])
            cleaned_line = _strip_section_label(current_section, match.group(2))
            if cleaned_line:
                sections[current_section].append(cleaned_line)
            continue

        bullet_match = re.match(r"^[-*•]\s*(.+)$", line)
        if current_section is not None and bullet_match:
            sections.setdefault(current_section, []).append(bullet_match.group(1).strip())
            continue

        if current_section is not None:
            sections.setdefault(current_section, []).append(line)

    return {
        section_number: "\n".join(content).strip()
        for section_number, content in sections.items()
        if content
    }


def _strip_section_label(section_number: int, text: str) -> str:
    """Remove the echoed question label from a numbered answer."""
    label_patterns = {
        1: (
            r"^(preferred\s+contact\s+time|"
            r"when(?:\s+would\s+you\s+like\s+your\s+rm\s+to\s+contact\s+you)?)\s*[:\-]?\s*"
        ),
        2: (
            r"^(meeting\s+format|where|online\s+or\s+in-?person|"
            r"would\s+you\s+prefer.*?)\s*[:\-]?\s*"
        ),
        3: r"^(agenda|what\s+agenda\s+should\s+your\s+rm\s+prepare\s+for)\s*[:\-]?\s*",
        4: (
            r"^(top\s*3\s*(things|outcomes)?|outcomes|goals|"
            r"what\s+are\s+the\s+top\s+3.*?)\s*[:\-]?\s*"
        ),
    }
    pattern = label_patterns.get(section_number)
    if not pattern:
        return text.strip()
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def _extract_preferred_time(user_message: str, section_text: str | None) -> str | None:
    """Extract a preferred contact timing from a reply."""
    candidate = _clean_text(section_text)
    if candidate:
        return candidate

    for sentence in re.split(r"(?<=[.!?])\s+", user_message):
        normalized = sentence.strip()
        lower_sentence = normalized.lower()
        if any(keyword in lower_sentence for keyword in _TIME_KEYWORDS):
            return normalized
    return None


def _extract_meeting_format(
    user_message: str,
    section_text: str | None,
) -> Literal["online", "in-person"] | None:
    """Normalize the meeting format preference."""
    candidate = (section_text or user_message).lower()
    in_person_terms = ["in person", "in-person", "face to face", "face-to-face"]
    online_terms = ["online", "virtual", "zoom", "teams", "video", "call"]
    if any(term in candidate for term in in_person_terms):
        return MEETING_FORMAT_IN_PERSON
    if any(term in candidate for term in online_terms):
        return MEETING_FORMAT_ONLINE
    return None


def _extract_agenda(user_message: str, section_text: str | None) -> str | None:
    """Extract the agenda the RM should prepare for."""
    candidate = _clean_text(section_text)
    if candidate:
        return candidate

    patterns = [
        r"(?:agenda|discuss|review|talk about|meeting about)\s*[:\-]?\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_message, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return None


def _extract_top_outcomes(user_message: str, section_text: str | None) -> list[str]:
    """Extract up to three desired meeting outcomes."""
    if section_text:
        outcomes = _split_outcomes(section_text)
        if outcomes:
            return outcomes

    bullet_outcomes = [
        _clean_text(match.group(1))
        for match in re.finditer(r"^[-*•]\s+(.+)$", user_message, flags=re.MULTILINE)
    ]
    bullet_outcomes = [item for item in bullet_outcomes if item]
    if bullet_outcomes:
        return bullet_outcomes[:3]

    patterns = [
        r"(?:top\s*3|outcomes|goals|want to get out of the meeting)\s*[:\-]?\s*(.+)",
        r"i want to\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_message, flags=re.IGNORECASE)
        if match:
            outcomes = _split_outcomes(match.group(1))
            if outcomes:
                return outcomes
    return []


def _split_outcomes(text: str) -> list[str]:
    """Split a free-text outcomes string into up to three concise outcomes."""
    parts = re.split(r"\s*(?:\n|;|,|\band\b)\s*", text)
    cleaned = [_clean_text(part) for part in parts]
    cleaned = [part for part in cleaned if part]
    deduped: list[str] = []
    for part in cleaned:
        if part not in deduped:
            deduped.append(part)
    return deduped[:3]


def _format_recent_conversation(conversation_history: list[dict[str, str]]) -> str:
    """Format the recent conversation as a short transcript for extraction or summary."""
    recent_messages = conversation_history[-10:]
    lines = [
        f"{message['role'].capitalize()}: {message['content']}"
        for message in recent_messages
        if message.get("content")
    ]
    return "\n".join(lines)


def _collect_recent_user_context(
    conversation_history: list[dict[str, str]],
    trigger_message: str,
) -> str:
    """Collect a short snippet of recent user context relevant to the RM handoff."""
    recent_user_messages = [
        message["content"].strip()
        for message in conversation_history[-8:]
        if message.get("role") == "user" and message.get("content")
    ]
    filtered = [message for message in recent_user_messages if message != trigger_message]
    context_parts = filtered[-2:]
    if trigger_message:
        context_parts.insert(0, trigger_message)
    compact = []
    for part in context_parts:
        short_part = _clean_text(part)
        if short_part and short_part not in compact:
            compact.append(short_part)
    return " ".join(compact[:3])


def _clean_text(value: str | None) -> str | None:
    """Normalize whitespace and trailing punctuation in extracted text."""
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" .,:;-")
    return cleaned or None


def _build_metadata() -> dict[str, list[Any]]:
    """Return fresh metadata containers for assistant messages."""
    return {"metrics": [], "suggestions": []}


def _utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()
