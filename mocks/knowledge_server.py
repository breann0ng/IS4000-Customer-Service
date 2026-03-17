"""Mock MCP server for Knowledge Systems (port 9002).

Serves: private_banking, compliance_tax, knowledge_query tools.

Run standalone:
    uv run uvicorn mocks.knowledge_server:app --host 0.0.0.0 --port 9002
"""

from mocks.base import create_mock_mcp_app

MOCK_ACCOUNTS = [
    {"account": "CH93 0076 2011 6238 5295 7", "currency": "CHF", "balance": "2,345,678.50"},
    {"account": "CH93 0076 2011 6238 5296 8", "currency": "EUR", "balance": "1,123,456.00"},
    {"account": "CH93 0076 2011 6238 5297 9", "currency": "USD", "balance": "3,456,789.25"},
    {"account": "CH93 0076 2011 6238 5298 0", "currency": "GBP", "balance": "567,890.75"},
]

TOOL_DEFINITIONS = [
    {
        "name": "private_banking",
        "description": "Private banking operations for account management and transactions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
    {
        "name": "compliance_tax",
        "description": "Compliance and tax reporting operations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "retrieved_documents": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
    {
        "name": "knowledge_query",
        "description": "Knowledge base query for policies and product information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "retrieved_documents": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
]


def handle_private_banking(params: dict) -> dict:
    """Generate a mock private banking response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    account_lines = "\n".join(
        f"  - {account['account']} ({account['currency']}): {account['balance']}"
        for account in MOCK_ACCOUNTS
    )
    total_chf = "7,493,814.50"
    return {
        "response": (
            f"Account Summary:\n\n{account_lines}\n"
            f"  Total (CHF equivalent): {total_chf}\n\n"
            f"Regarding: {task[:120]}\n\n"
            f"The requested transaction has been noted and will be processed within "
            f"the standard settlement window. For domestic CHF transfers, settlement "
            f"is same-day if submitted before 15:00 CET. Cross-border transfers "
            f"require 1-2 business days depending on the destination corridor.\n\n"
            f"A confirmation will be sent to your registered secure channel upon settlement. "
            f"For urgent transfers exceeding CHF 1,000,000, your relationship manager "
            f"can authorize priority processing."
        )
    }


def handle_compliance_tax(params: dict) -> dict:
    """Generate a mock compliance and tax response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    retrieved = params.get("retrieved_documents", "")
    context_note = ""
    if retrieved and retrieved != "No relevant regulatory documents found.":
        context_note = (
            "\n\nRelevant policy references have been consulted in preparing this response."
        )
    return {
        "response": (
            f"Compliance & Tax Assessment: {task[:120]}\n\n"
            f"Current compliance status: FULLY COMPLIANT\n"
            f"Last KYC review: 15 September 2025 (valid until September 2028)\n"
            f"CRS reporting status: Up to date\n"
            f"FATCA classification: Certified, W-8BEN on file\n\n"
            f"Key upcoming dates:\n"
            f"  - CRS reporting deadline: 30 June 2026\n"
            f"  - Annual tax certificate: Available January 2027\n"
            f"  - WHT reclaim window: January - June 2026\n"
            f"  - Next periodic KYC review: September 2028\n\n"
            f"For jurisdiction-specific tax advice, we recommend consulting with "
            f"your personal tax advisor. We can facilitate a joint meeting with "
            f"our in-house tax specialists if required."
            f"{context_note}"
        )
    }


def handle_knowledge_query(params: dict) -> dict:
    """Generate a mock knowledge query response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "response": (
            f"Knowledge Base Result: {task[:120]}\n\n"
            f"Based on our current policies and product documentation:\n\n"
            f"UBS Wealth Management provides comprehensive services tailored to "
            f"HNWI clients, including discretionary and advisory mandates, "
            f"structured products, and access to exclusive investment opportunities. "
            f"All services are subject to suitability assessment and regulatory "
            f"compliance requirements.\n\n"
            f"For the most current terms and conditions, please consult with your "
            f"relationship manager who can provide the latest documentation."
        )
    }


TOOL_HANDLERS = {
    "private_banking": handle_private_banking,
    "compliance_tax": handle_compliance_tax,
    "knowledge_query": handle_knowledge_query,
}

app = create_mock_mcp_app(
    title="Mock Knowledge MCP Server",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers=TOOL_HANDLERS,
)
