"""Helpers for appending targeted follow-up questions to assistant replies."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

RM_FOLLOW_UP_PROMPT = "Would you like me to help schedule an appointment with your RM?"
RM_FOLLOW_UP_CONTEXT_KEY = "rm_follow_up"

_RM_QUERY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bhow\s+do\s+i\s+contact\s+my\s+(rm|relationship\s+manager)\b",
        r"\bhow\s+can\s+i\s+contact\s+my\s+(rm|relationship\s+manager)\b",
        r"\bhow\s+do\s+i\s+reach\s+my\s+(rm|relationship\s+manager)\b",
        r"\bhow\s+can\s+i\s+reach\s+my\s+(rm|relationship\s+manager)\b",
        r"\bcontact\s+my\s+(rm|relationship\s+manager)\b",
        r"\breach\s+my\s+(rm|relationship\s+manager)\b",
        r"\bspeak\s+to\s+my\s+(rm|relationship\s+manager)\b",
        r"\bbook\s+a\s+meeting\s+with\s+my\s+(rm|relationship\s+manager)\b",
        r"\bschedule\s+a\s+review\s+with\s+my\s+(rm|relationship\s+manager)\b",
        r"\barrange\s+a\s+review\s+with\s+my\s+(rm|relationship\s+manager)\b",
        r"\bset\s+up\s+a\s+(meeting|call|review)\s+with\s+my\s+(rm|relationship\s+manager)\b",
    ]
]

_RM_RESPONSE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"secure\s+message\s+channel",
        r"relationship\s+manager\s+directly",
        r"contact\s+your\s+relationship\s+manager",
        r"contact\s+your\s+rm",
        r"your\s+relationship\s+manager\s+will\s+be\s+in\s+touch",
        r"please\s+contact\s+your\s+(rm|relationship\s+manager)",
        r"reach\s+your\s+relationship\s+manager",
        r"message\s+your\s+relationship\s+manager",
    ]
]

_ALREADY_ASKING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"would\s+you\s+like\s+me\s+to\s+help\s+schedule",
        r"would\s+you\s+like\s+me\s+to\s+help\s+you\s+schedule",
        r"would\s+you\s+like\s+me\s+to\s+book",
        r"do\s+you\s+want\s+me\s+to\s+help\s+schedule",
        r"can\s+i\s+help\s+schedule",
    ]
]

_AFFIRMATIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        (
            r"^\s*(yes|yeah|yep|sure|ok|okay|"
            r"please do|please help|"
            r"absolutely|sounds good)\s*[.!?]*\s*$"
        ),
        r"^\s*(yes please|sure please|yes, please|please do)\s*[.!?]*\s*$",
        r"^\s*(go ahead|let's do it|lets do it)\s*[.!?]*\s*$",
    ]
]


def apply_rm_follow_up(
    user_message: str,
    assistant_response: str,
    suggestions: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Append an RM scheduling follow-up when the message or response indicates RM contact."""
    if _already_contains_follow_up(assistant_response):
        return assistant_response, suggestions or []

    if not _should_offer_rm_follow_up(user_message, assistant_response):
        return assistant_response, suggestions or []

    updated_response = (
        f"{assistant_response}\n\n{RM_FOLLOW_UP_PROMPT}"
        if assistant_response.strip()
        else RM_FOLLOW_UP_PROMPT
    )
    updated_suggestions = list(suggestions or [])
    if RM_FOLLOW_UP_PROMPT not in updated_suggestions:
        updated_suggestions.append(RM_FOLLOW_UP_PROMPT)
    return updated_response, updated_suggestions


def build_rm_follow_up_context(trigger_message: str) -> dict[str, Any]:
    """Build a persistent marker that a follow-up question is awaiting confirmation."""
    return {
        "pending_confirmation": True,
        "prompt": RM_FOLLOW_UP_PROMPT,
        "trigger_message": trigger_message,
    }


def get_pending_rm_follow_up(session_messages: Sequence[Any]) -> dict[str, Any] | None:
    """Return the latest pending RM follow-up marker, if one exists."""
    for message in reversed(session_messages):
        if getattr(message, "role", None) != "assistant":
            continue
        context = getattr(message, "context", None) or {}
        pending = context.get(RM_FOLLOW_UP_CONTEXT_KEY)
        if isinstance(pending, dict) and pending.get("pending_confirmation"):
            return pending
        content = getattr(message, "content", "") or ""
        if RM_FOLLOW_UP_PROMPT in content:
            metadata = context.get("metadata") or {}
            if isinstance(metadata, dict) and RM_FOLLOW_UP_PROMPT in metadata.get(
                "suggestions", []
            ):
                return {
                    "pending_confirmation": True,
                    "prompt": RM_FOLLOW_UP_PROMPT,
                    "trigger_message": context.get("trigger_message") or "",
                }
    return None


def is_affirmative_rm_follow_up_response(message: str) -> bool:
    """Return True when the user's reply looks like an affirmative confirmation."""
    normalized = message.strip().lower()
    return bool(normalized) and any(pattern.search(normalized) for pattern in _AFFIRMATIVE_PATTERNS)


def _should_offer_rm_follow_up(user_message: str, assistant_response: str) -> bool:
    """Return True when the current exchange is about contacting or meeting an RM."""
    combined_text = f"{user_message}\n{assistant_response}"
    if any(pattern.search(combined_text) for pattern in _RM_QUERY_PATTERNS):
        return True
    return any(pattern.search(assistant_response) for pattern in _RM_RESPONSE_PATTERNS)


def _already_contains_follow_up(assistant_response: str) -> bool:
    """Avoid duplicating the same RM scheduling prompt twice."""
    return any(pattern.search(assistant_response) for pattern in _ALREADY_ASKING_PATTERNS)
