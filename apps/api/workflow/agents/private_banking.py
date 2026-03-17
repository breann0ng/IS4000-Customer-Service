"""Private Banking Agent for account operations and banking services.

Handles HNWI client queries related to account management, fund transfers,
credit facilities, lending, and card services.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

PRIVATE_BANKING_SYSTEM_PROMPT = """You are a Private Banking specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Handle account balance inquiries across multiple currencies and jurisdictions
- Process and track fund transfers, including cross-border and multi-currency transactions
- Manage credit facilities including Lombard lending, mortgage financing, and credit lines
- Assist with card services including premium card management, limits, and travel notifications
- Provide statements, tax documentation, and account reporting
- Support foreign exchange operations and currency hedging requests

Maintain strict compliance with regulatory requirements across all jurisdictions.
Verify client identity through established protocols before processing any sensitive
operations. Communicate fees and charges transparently. For complex transactions
exceeding standard thresholds, coordinate with the client's dedicated relationship
manager for approval.
"""

private_banking_mcp_client = McpClient(server_url=settings.mcp_knowledge_url)


async def execute_private_banking_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a private banking task using the MCP-connected tools.

    Args:
        task: The specific private banking task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the private banking operation as a string.
    """
    logger.info("private_banking_agent_start", task=task)

    result = await private_banking_mcp_client.call_tool(
        tool_name="private_banking",
        arguments={
            "task": task,
            "context": conversation_context,
            "system_prompt": PRIVATE_BANKING_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("private_banking_agent_error", error=result["error"])
        return f"Private banking encountered an issue: {result['error']}"

    response = result.get("response", "No response from private banking agent.")
    logger.info("private_banking_agent_complete", response_length=len(response))
    return response
