"""Mock MCP server for Service Workflow Systems (port 9003).

Serves: client_services, fx_treasury, service_workflow tools.

Run standalone:
    uv run uvicorn mocks.service_workflow_server:app --host 0.0.0.0 --port 9003
"""

import random

from mcp_servers.base import create_mock_mcp_app, get_persona_data

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
                "username": {"type": "string"},
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
                "username": {"type": "string"},
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
                "username": {"type": "string"},
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
    username = params.get("username", "jsmith")
    persona_data = get_persona_data(username) or {}
    profile = persona_data.get("profile", {})
    full_name = profile.get("full_name", "Valued Client")
    rm_name = profile.get("relationship_manager", "your Relationship Manager")

    # Check if this is a greeting task
    if any(greet in task.lower() for greet in ["greeting", "welcome", "hello", "hi"]):
        return {
            "agent_name": "client_services",
            "response": (
                f"Good day, {full_name}. It is a pleasure to assist you. As your premium wealth management "
                "assistant at UBS, I am dedicated to providing you with seamless access to our global "
                "capabilities."
            ),
            "status": "COMPLETED",
            "next_steps": [
                "Portfolio Performance & Insights Review",
                "Account Balances & Transactions Support",
                "Lending & Credit Consultations"
            ],
            "metrics": [],
            "requires_escalation": False,
            "raw_data": {"profile": profile}
        }

    reference_number = f"CS-{random.randint(100000, 999999)}"
    retrieved = params.get("retrieved_documents", "")
    policy_note = ""
    if retrieved and retrieved != "No relevant policy documents found.":
        policy_note = "Internal policies reviewed."

    return {
        "agent_name": "client_services",
        "response": f"Service Request {reference_number} has been registered for: {task[:60]}...",
        "status": "IN_PROGRESS",
        "next_steps": [
            f"{rm_name} will review your request",
            "Documentation requirements will be shared via secure message",
            "You will receive status updates at each milestone"
        ],
        "metrics": [],
        "requires_escalation": False,
        "raw_data": {
            "reference_number": reference_number,
            "assigned_to": rm_name,
            "estimated_completion": "2-3 business days",
            "policy_reviewed": policy_note != ""
        }
    }



def handle_fx_treasury(params: dict) -> dict:
    """Generate a mock FX and treasury response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "agent_name": "fx_treasury",
        "response": f"Indicative foreign exchange and treasury report generated for: {task[:60]}...",
        "status": "COMPLETED",
        "next_steps": [
            "Contact your FX advisor for a tailored hedging proposal",
            "Review transaction execution guidelines for staged execution"
        ],
        "metrics": [],
        "requires_escalation": False,
        "raw_data": {
            "indicative_rates": MOCK_FX_RATES,
            "execution_thresholds": {
                "auto": 500000,
                "preferential": 2000000
            }
        }
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
        "agent_name": "service_workflow",
        "response": f"General service workflow {reference_number} has been initiated.",
        "status": "IN_PROGRESS",
        "next_steps": [
            "Routing to appropriate team for processing",
            "Await confirmation within 1 business day"
        ],
        "metrics": [],
        "requires_escalation": False,
        "raw_data": {
            "reference_number": reference_number,
            "task_preview": task[:120]
        }
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
