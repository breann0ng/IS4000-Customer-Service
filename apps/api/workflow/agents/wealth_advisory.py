"""Wealth Advisory Agent for portfolio management and investment guidance.

Handles HNWI client queries related to portfolio performance, asset allocation,
market insights, structured products, and investment strategy.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

WEALTH_ADVISORY_SYSTEM_PROMPT = """You are a Wealth Advisory specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Provide portfolio performance summaries and detailed asset allocation breakdowns
- Offer investment strategy recommendations aligned with the client's risk profile and goals
- Deliver market insights, economic outlook briefings, and sector analysis
- Explain structured products, alternative investments, and bespoke solutions
- Discuss estate planning considerations and intergenerational wealth transfer strategies
- Review and recommend adjustments to existing investment mandates

Always maintain the highest standards of discretion and professionalism expected in
private wealth management. Present information clearly and with appropriate caveats
about market risks. Refer to the client's relationship manager for execution of any
trades or mandate changes. Never provide specific buy/sell recommendations without
proper suitability assessment context.
"""

wealth_advisory_mcp_client = McpClient(server_url=settings.mcp_banking_ops_url)


async def execute_wealth_advisory_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a wealth advisory task using the MCP-connected tools.

    Args:
        task: The specific wealth advisory task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the wealth advisory operation as a string.
    """
    logger.info("wealth_advisory_agent_start", task=task)

    result = await wealth_advisory_mcp_client.call_tool(
        tool_name="wealth_advisory",
        arguments={
            "task": task,
            "context": conversation_context,
            "system_prompt": WEALTH_ADVISORY_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("wealth_advisory_agent_error", error=result["error"])
        return f"Wealth advisory encountered an issue: {result['error']}"

    response = result.get("response", "No response from wealth advisory agent.")
    logger.info("wealth_advisory_agent_complete", response_length=len(response))
    return response
