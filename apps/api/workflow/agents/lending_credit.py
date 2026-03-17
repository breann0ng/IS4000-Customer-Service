"""Lending & Credit Agent for loan facilities and structured financing.

Handles HNWI client queries related to Lombard lending, mortgage financing,
credit lines, structured lending solutions, and margin facilities.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

LENDING_CREDIT_SYSTEM_PROMPT = """You are a Lending & Credit specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Evaluate and structure Lombard lending facilities against investment portfolios
- Process mortgage financing applications for residential and commercial properties
- Manage revolving credit lines and overdraft facilities
- Design structured lending solutions for complex asset-backed financing needs
- Provide margin facility management for leveraged investment strategies
- Explain lending terms, covenants, LTV ratios, and interest rate structures
- Coordinate with legal and compliance for loan documentation and approvals
- Monitor existing credit facilities and alert on covenant or margin triggers

Present lending options with full transparency on rates, fees, and risk implications.
Ensure all recommendations comply with internal credit policies and regulatory requirements.
For facilities above standard thresholds, coordinate with the credit committee for approval.
Always discuss the risks of leveraged positions and margin calls with clients.
"""

lending_credit_mcp_client = McpClient(server_url=settings.mcp_banking_ops_url)


async def execute_lending_credit_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a lending and credit task using the MCP-connected tools.

    Args:
        task: The specific lending or credit task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the lending operation as a string.
    """
    logger.info("lending_credit_agent_start", task=task)

    result = await lending_credit_mcp_client.call_tool(
        tool_name="lending_credit",
        arguments={
            "task": task,
            "context": conversation_context,
            "system_prompt": LENDING_CREDIT_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("lending_credit_agent_error", error=result["error"])
        return f"Lending & credit encountered an issue: {result['error']}"

    response = result.get("response", "No response from lending & credit agent.")
    logger.info("lending_credit_agent_complete", response_length=len(response))
    return response
