"""FX & Treasury Agent for foreign exchange and multi-currency management.

Handles HNWI client queries related to currency exchange, hedging strategies,
multi-currency account management, and treasury products.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

FX_TREASURY_SYSTEM_PROMPT = """\
You are a Foreign Exchange & Treasury specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Execute and quote foreign exchange transactions across all major and emerging market currencies
- Design and implement currency hedging strategies to protect portfolio value
- Manage multi-currency account structures and optimize currency allocation
- Provide FX market insights, rate forecasts, and currency risk analysis
- Structure forward contracts, options, and other FX derivatives for hedging or positioning
- Advise on optimal timing and execution strategies for large currency conversions
- Support treasury management including cash pooling and liquidity optimization
- Manage cross-currency payment flows and correspondent banking arrangements

Provide competitive rates and transparent pricing on all FX transactions. Clearly
communicate market risks, counterparty exposure, and the implications of hedging costs.
For large transactions, recommend staged execution to minimize market impact.
Present all options with clear risk/reward profiles and ensure client understanding
before execution.
"""

fx_treasury_mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)


async def execute_fx_treasury_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a foreign exchange or treasury task using the MCP-connected tools.

    Args:
        task: The specific FX or treasury task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the FX/treasury operation as a string.
    """
    logger.info("fx_treasury_agent_start", task=task)

    result = await fx_treasury_mcp_client.call_tool(
        tool_name="fx_treasury",
        arguments={
            "task": task,
            "context": conversation_context,
            "system_prompt": FX_TREASURY_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("fx_treasury_agent_error", error=result["error"])
        return f"FX & treasury encountered an issue: {result['error']}"

    response = result.get("response", "No response from FX & treasury agent.")
    logger.info("fx_treasury_agent_complete", response_length=len(response))
    return response
