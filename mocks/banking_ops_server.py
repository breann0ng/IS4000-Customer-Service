"""Mock MCP server for Banking Operations (port 9001).

Serves: wealth_advisory, lending_credit, banking_operation tools.

Run standalone:
    uv run uvicorn mocks.banking_ops_server:app --host 0.0.0.0 --port 9001
"""

from mocks.base import create_mock_mcp_app

MOCK_PORTFOLIO: dict[str, str | dict[str, str]] = {
    "total_aum": "CHF 12,450,000",
    "asset_allocation": {
        "Equities": "42% (CHF 5,229,000)",
        "Fixed Income": "28% (CHF 3,486,000)",
        "Alternatives": "15% (CHF 1,867,500)",
        "Cash & Equivalents": "10% (CHF 1,245,000)",
        "Real Estate": "5% (CHF 622,500)",
    },
    "ytd_performance": "+6.8%",
    "benchmark_comparison": "+1.2% vs. benchmark",
}

TOOL_DEFINITIONS = [
    {
        "name": "wealth_advisory",
        "description": "Wealth advisory operations for HNWI portfolio and investment queries",
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
        "name": "lending_credit",
        "description": "Lending and credit facility operations",
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
        "name": "banking_operation",
        "description": "General banking operations",
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


def handle_wealth_advisory(params: dict) -> dict:
    """Generate a mock wealth advisory response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    portfolio = MOCK_PORTFOLIO
    asset_allocation = portfolio["asset_allocation"]
    assert isinstance(asset_allocation, dict)
    allocation_lines = "\n".join(
        f"  - {asset_class}: {allocation}" for asset_class, allocation in asset_allocation.items()
    )
    return {
        "response": (
            f"Portfolio Overview:\n\n"
            f"Total Assets Under Management: {portfolio['total_aum']}\n"
            f"Year-to-Date Performance: {portfolio['ytd_performance']} "
            f"({portfolio['benchmark_comparison']})\n\n"
            f"Current Asset Allocation:\n{allocation_lines}\n\n"
            f"Regarding your query: {task[:120]}\n\n"
            f"Our investment committee maintains a moderately constructive outlook "
            f"on global equities with a preference for quality growth names. "
            f"We recommend reviewing your allocation with your relationship manager "
            f"during your next quarterly review. Current market conditions suggest "
            f"maintaining the existing strategic allocation with tactical adjustments "
            f"towards defensive sectors."
        )
    }


def handle_lending_credit(params: dict) -> dict:
    """Generate a mock lending and credit response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "response": (
            f"Lending Assessment for your inquiry: {task[:120]}\n\n"
            f"Based on your portfolio valuation of {MOCK_PORTFOLIO['total_aum']}, "
            f"the following credit facilities are available:\n\n"
            f"Lombard Credit Line:\n"
            f"  - Maximum facility: CHF 8,715,000 (70% LTV on diversified portfolio)\n"
            f"  - Indicative rate: SARON + 0.85% p.a.\n"
            f"  - Arrangement fee: 0.10% (waived for existing premium clients)\n"
            f"  - Flexible drawdown and repayment, no fixed maturity\n\n"
            f"Mortgage Financing:\n"
            f"  - Fixed 5-year: 1.35% p.a.\n"
            f"  - Fixed 10-year: 1.45% p.a.\n"
            f"  - Variable (SARON-linked): SARON + 0.65% p.a.\n"
            f"  - Maximum LTV: 80% (residential), 65% (commercial)\n\n"
            f"A detailed credit proposal can be prepared within 48 hours. "
            f"Please confirm if you would like to proceed."
        )
    }


def handle_banking_operation(params: dict) -> dict:
    """Generate a mock general banking response.

    Args:
        params: Tool invocation arguments.

    Returns:
        A dictionary with the mock response.
    """
    task = params.get("task", "")
    return {
        "response": (
            f"Banking operation processed for: {task[:120]}\n\n"
            f"The requested operation has been queued for processing. "
            f"Standard operations are completed within the same business day. "
            f"Cross-border transactions may require 1-2 additional business days."
        )
    }


TOOL_HANDLERS = {
    "wealth_advisory": handle_wealth_advisory,
    "lending_credit": handle_lending_credit,
    "banking_operation": handle_banking_operation,
}

app = create_mock_mcp_app(
    title="Mock Banking Ops MCP Server",
    tool_definitions=TOOL_DEFINITIONS,
    tool_handlers=TOOL_HANDLERS,
)
