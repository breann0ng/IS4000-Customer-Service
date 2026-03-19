"""Escalation node for the LangGraph workflow.

Implements a hardcoded RegEx-based escalation matrix that detects
advisory, transactional, or high-distress queries and bypasses the
normal executor/synthesizer flow, routing directly to a human RM.

From the architecture spec:
- "What should I invest in?" → RM Only
- Trust / Legal / Tax structure → RM Only
- High distress / Complaints → RM Only
"""

import re

from apps.api.logging_config import get_logger
from apps.api.workflow.state import WorkflowState

logger = get_logger(__name__)

# ── Escalation Patterns ───────────────────────────────────────────────────────
# These patterns detect queries that cross from INFORMATIONAL to ADVISORY.

_ESCALATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        # Advisory / Investment recommendations
        r"what\s+should\s+i\s+invest",
        r"should\s+i\s+(buy|sell|hold)",
        r"recommend\s+(me\s+)?(a|an|some)?\s*(stock|bond|fund|investment|portfolio)",
        r"give\s+me\s+(investment\s+)?advice",
        r"which\s+(stock|fund|etf|bond)s?\s+should\s+i",
        r"is\s+it\s+a\s+good\s+time\s+to\s+(buy|sell|invest)",
        r"rebalance\s+my\s+portfolio",
        # Trust / Legal / Tax structuring
        r"(set\s+up|create|establish)\s+(a\s+)?(trust|foundation|holding\s+company)",
        r"tax\s+(planning|structuring|optimization|avoidance|strategy)",
        r"(estate|inheritance|succession)\s+planning",
        r"legal\s+structure",
        r"offshore\s+(account|structure|trust)",
        # High distress / Complaints
        r"(i\s+want\s+to\s+)?complain",
        r"(this\s+is\s+)?unacceptable",
        r"speak\s+to\s+(a\s+)?(manager|supervisor|senior)",
        r"i('m|\s+am)\s+(very\s+)?(upset|angry|frustrated|disappointed|furious)",
        r"lost\s+(a\s+lot\s+of\s+)?money",
        r"sue|lawsuit|legal\s+action",
        r"close\s+(all\s+)?(my\s+)?account",
        r"regulatory\s+(complaint|report|authority)",
    ]
]

ESCALATION_RESPONSE = (
    "Thank you for your query. This type of request requires personalised attention "
    "from your dedicated Relationship Manager, who can provide tailored advice "
    "aligned with your specific financial situation and regulatory requirements.\n\n"
    "I have flagged this as a priority item. Your Relationship Manager will be "
    "in touch within one business day. If you need immediate assistance, please "
    "contact the UBS Private Banking concierge at +41 44 234 1111.\n\n"
    "In the meantime, I'm happy to help with informational queries about your "
    "portfolio performance, account balances, or market outlook."
)


def check_escalation(user_message: str) -> bool:
    """Check if the user message triggers the escalation matrix.

    Args:
        user_message: The user's input message.

    Returns:
        True if the message matches an escalation pattern, False otherwise.
    """
    for pattern in _ESCALATION_PATTERNS:
        if pattern.search(user_message):
            logger.info(
                "escalation_triggered",
                pattern=pattern.pattern,
                message_preview=user_message[:100],
            )
            return True
    return False


async def escalation_node(state: WorkflowState) -> dict:
    """Return a canned escalation response and flag for RM routing.

    Bypasses the normal executor and synthesizer flow entirely.

    Args:
        state: The current workflow state.

    Returns:
        A dictionary with the escalation response and flag.
    """
    logger.info("escalation_node_triggered", user_message=state.user_message[:100])
    return {
        "final_response": ESCALATION_RESPONSE,
        "is_escalated": True,
    }
