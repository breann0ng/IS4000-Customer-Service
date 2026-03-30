import asyncio
import random

from langchain_community.tools.tavily_search import TavilySearchResults

from apps.api.config import settings
from apps.api.customers.data_service import DataService
from mcp_servers.base import create_mock_mcp_app

TOOL_DEFINITIONS = [
    {
        "name": "client_services",
        "description": "Client services for onboarding, KYC, appointments, and escalations",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context": {"type": "string"},
                "customer_id": {"type": "string"},
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
                "customer_id": {"type": "string"},
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
                "customer_id": {"type": "string"},
                "system_prompt": {"type": "string"},
            },
        },
    },
]


async def _fetch_tavily(task: str) -> str:
    """Fetch live market data using Tavily API."""
    if settings.is_llm_mock_mode or not settings.tavily_api_key:
        return "No live market data retrieved."
    try:
        search = TavilySearchResults(max_results=3)
        results = await asyncio.wait_for(search.ainvoke(task), timeout=5.0)
        return str(results)
    except Exception as e:
        print(f"Tavily search failed: {e}")
    return "No live market data retrieved."


async def handle_client_services(params: dict) -> dict:
    """Generate a mock client services response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    customer_id = params.get("customer_id", "C-011")
    summary = DataService.get_customer_summary(customer_id)
    planning = DataService.get_financial_planning(customer_id)
    
    pref_name = "Client"
    if summary and "profile" in summary:
        pref_name = (summary["profile"] or {}).get("preferred_name", (summary["profile"] or {}).get("full_name", "Client"))

    # Check if this is a performance query (fallback handler needs to answer this in mock mode)
    if "performance" in task.lower() or "return" in task.lower():
        ytd = summary.get("portfolio_summary", {}).get("ytd_return", "N/A")
        return {
            "response": (
                f"I've retrieved your current portfolio performance, {pref_name}.\n\n"
                f"Your Year-to-Date (YTD) return is currently **{ytd}%**.\n\n"
                f"This align with your stated goals: {planning.get('goals')[:1]}...\n\n"
                f"Would you like a deeper breakdown from our Wealth Advisory team?"
            )
        }

    # Check if this is a greeting task
    if any(greet in task.lower() for greet in ["greeting", "welcome", "hello", "hi"]):
        return {
            "response": (
                f"Good day, {pref_name}. It is a pleasure to assist you. As your premium wealth management "
                "assistant, I am dedicated to providing you with seamless access to our global "
                "capabilities.\n\n"
                "I can assist you with a wide range of services today, including:\n\n"
                "1. **Portfolio Performance & Insights**: A comprehensive review of your current "
                "asset allocation and YTD performance.\n"
                "2. **Account Balances & Transactions**: Securely check your multi-currency "
                "positions or manage global transfers.\n"
                "3. **Lending & Credit Options**: Explore bespoke Lombard lending solutions "
                "designed to optimize your liquidity.\n\n"
                "How may I be of service to you today?"
            )
        }

    # Fetch live information if the task seems to require general knowledge/market data
    market_info = await _fetch_tavily(task)

    reference_number = f"CS-{random.randint(100000, 999999)}"
    retrieved = params.get("retrieved_documents", "")
    policy_note = ""
    if retrieved and retrieved != "No relevant policy documents found.":
        policy_note = "\n\nRelevant internal policies have been reviewed for this request."
    
    return {
        "response": (
            f"Service Request Registered: {reference_number}\n\n"
            f"Request: {task[:120]}\n\n"
            f"Client Goals Context: {planning.get('goals')[:2]}...\n\n"
            f"Market/Service Context:\n{market_info[:300]}...\n\n"
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


async def handle_fx_treasury(params: dict) -> dict:
    """Generate a mock FX and treasury response using live market data.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    
    # Fetch live FX rates and treasury info using Tavily
    market_data = await _fetch_tavily(f"Current FX rates and treasury insights for: {task}")

    return {
        "response": (
            f"FX & Treasury Report (Live Search)\n\n"
            f"Market Intelligence:\n{market_data[:500]}...\n\n"
            f"Regarding: {task[:120]}\n\n"
            f"Execution Guidelines:\n"
            f"  - Transactions up to USD 500,000: Automatic best execution\n"
            f"  - USD 500,000 - 2,000,000: Preferential desk pricing available\n"
            f"  - Above USD 2,000,000: Staged execution recommended\n\n"
            f"Hedging Options:\n"
            f"  - Forward contracts: Available for 1M to 24M tenors\n"
            f"  - Vanilla options: Premium quoted on request\n"
            f"  - Zero-cost collars: Structured to client specifications\n\n"
            f"Contact your FX advisor for a tailored hedging proposal based on these live market rates."
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
