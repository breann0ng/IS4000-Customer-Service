"""Input guard middleware for PII masking and prompt injection detection.

Implements the Zero-Trust Security Pipeline from the architecture spec:
- Masks NRIC numbers (Singapore format)
- Masks account numbers (8-20 digit sequences)
- Blocks prompt injection attempts
"""

import re

from apps.api.logging_config import get_logger

logger = get_logger(__name__)

# ── PII Patterns ──────────────────────────────────────────────────────────────

# Singapore NRIC/FIN: [STFGM] followed by 7 digits and a letter
_NRIC_PATTERN = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)

# Sequences of 8-20 digits that likely represent account numbers
_ACCOUNT_NUMBER_PATTERN = re.compile(r"\b\d{8,20}\b")

# ── Prompt Injection Patterns ─────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?prior\s+instructions",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+(all\s+)?previous",
        r"override\s+(all\s+)?system\s+prompt",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"show\s+(your\s+)?system\s+prompt",
        r"print\s+(your\s+)?system\s+prompt",
        r"output\s+(your\s+)?system\s+prompt",
        r"repeat\s+(your\s+)?instructions",
        r"you\s+are\s+now\s+(a|an)\s+",
        r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
        r"pretend\s+you\s+are\s+(?:not|no longer)\s+",
        r"jailbreak",
        r"DAN\s+mode",
    ]
]


def sanitize_input(text: str) -> str:
    """Mask PII patterns in user input.

    Replaces NRIC numbers with [NRIC_MASKED] and long digit sequences
    with [ACCOUNT_MASKED] to prevent sensitive data from reaching the LLM.

    Args:
        text: The raw user input.

    Returns:
        The input text with PII patterns masked.
    """
    original = text
    text = _NRIC_PATTERN.sub("[NRIC_MASKED]", text)
    text = _ACCOUNT_NUMBER_PATTERN.sub("[ACCOUNT_MASKED]", text)

    if text != original:
        logger.info("pii_masked", original_length=len(original), masked_length=len(text))

    return text


def check_prompt_injection(text: str) -> bool:
    """Check if the user input contains prompt injection attempts.

    Args:
        text: The user input to check.

    Returns:
        True if a prompt injection pattern was detected, False otherwise.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "prompt_injection_detected",
                pattern=pattern.pattern,
                input_preview=text[:100],
            )
            return True
    return False
