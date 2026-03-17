"""Mock MCP server for Service Workflow Systems (port 9003).

Serves: client_services, fx_treasury, service_workflow tools.

Run standalone:
    uv run uvicorn mocks.service_workflow_server:app --host 0.0.0.0 --port 9003
"""

import random

from mocks.base import create_mock_mcp_app

MOCK_FX_RATES = {
    "EUR/CHF": {"bid": "0.9412", "ask": "0.9418", "change": "-0.15%"},
    "USD/CHF": {"bid": "0.8823", "ask": "0.8829", "change": "+0.22%"},
    "GBP/CHF": {"bid": "1.1156", "ask": "1.1164", "change": "-0.08%"},
    "EUR/USD": {"bid": "1.0665", "ask": "1.0671", "change": "-0.37%"},
    "JPY/CHF": {"bid": "0.005912", "ask": "0.005918", "change": "+0.05%"},
    "CHF/SGD": {"bid": "1.5234", "ask": "1.5242", "change": "-0.12%"},
}

TOOL_DEFINITIONS = [
    {
        "name": "client_services",
        "description": "Client services for onboarding, KYC, appointments, and escalations",
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
        "name": "fx_treasury",
        "description": "Foreign exchange and treasury operations",
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
        "name": "service_workflow",
        "description": "General service workflow orchestration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
]


def handle_client_services(params: dict) -> dict:
    """Generate a mock client services response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    reference_number = f"CS-{random.randint(100000, 999999)}"
    retrieved = params.get("retrieved_documents", "")
    policy_note = ""
    if retrieved and retrieved != "No relevant policy documents found.":
        policy_note = "\n\nRelevant internal policies have been reviewed for this request."
    return {
        "response": (
            f"Service Request Registered: {reference_number}\n\n"
            f"Request: {task[:120]}\n\n"
            f"Status: IN PROGRESS\n"
            f"Estimated completion: 2-3 business days\n\n"
            f"Next steps:\n"
            f"  1. Your relationship manager has been notified\n"
            f"  2. Required documentation (if any) will be communicated via secure channel\n"
            f"  3. You will receive status updates at each milestone\n\n"
            f"For onboarding requests, please have the following ready:\n"
            f"  - Valid passport or national ID\n"
            f"  - Proof of address (dated within 3 months)\n"
            f"  - Source of wealth declaration\n\n"
            f"For urgent matters, contact your relationship manager directly or "
            f"call our priority service line."
            f"{policy_note}"
        )
    }


def handle_fx_treasury(params: dict) -> dict:
    """Generate a mock FX and treasury response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    rate_lines = "\n".join(
        f"  - {pair}: Bid {data['bid']} / Ask {data['ask']} ({data['change']})"
        for pair, data in MOCK_FX_RATES.items()
    )
    return {
        "response": (
            f"FX & Treasury Report\n\n"
            f"Current Indicative Rates (as of last refresh):\n{rate_lines}\n\n"
            f"Regarding: {task[:120]}\n\n"
            f"Execution Guidelines:\n"
            f"  - Transactions up to CHF 500,000: Automatic best execution\n"
            f"  - CHF 500,000 - 2,000,000: Preferential desk pricing available\n"
            f"  - Above CHF 2,000,000: Staged execution recommended\n\n"
            f"Hedging Options:\n"
            f"  - Forward contracts: Available for 1M to 24M tenors\n"
            f"  - Vanilla options: Premium quoted on request\n"
            f"  - Zero-cost collars: Structured to client specifications\n\n"
            f"Contact your FX advisor for a tailored hedging proposal."
        )
    }


def handle_service_workflow(params: dict) -> dict:
    """Generate a mock general service workflow response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    reference_number = f"SW-{random.randint(100000, 999999)}"
    return {
        "response": (
            f"Workflow Reference: {reference_number}\n\n"
            f"Request: {task[:120]}\n\n"
            f"The service workflow has been initiated. Your request is being "
            f"routed to the appropriate team for processing. You will receive "
            f"confirmation and next steps within 1 business day."
        )
    }


TOOL_HANDLERS = {
    "client_services": handle_client_services,
    "fx_treasury": handle_fx_treasury,
    "service_workflow": handle_service_workflow,
}

app = create_mock_mcp_app(
    title="Mock Service Workflow MCP Server",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers=TOOL_HANDLERS,
)
