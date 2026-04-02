"""Private Banking Agent for account operations and banking services.

Handles HNWI client queries related to account management, fund transfers,
credit facilities, lending, and card services.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

PRIVATE_BANKING_SYSTEM_PROMPT = """# ROLE
You are a Private Banking Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
1. Account Services: Multi-currency balances, transaction history, tax reporting data.
2. Payments & Transfers: Validation and status tracking.
3. Credit & Lending: Lombard lending, mortgage financing, credit lines.
4. Cards: Card limits, status, and travel notifications.

# GUIDELINES
- Provide structured, factual insights in JSON.
- Never execute, simulate, or confirm transactions.
- Include "requires_verification": true for sensitive operations.
"""

async def execute_private_banking_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a private banking task using the MCP-connected tools.

    Args:
        task: The specific private banking task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the private banking operation as a SpecialistAgentOutput.
    """
    logger.info("private_banking_agent_start", task=task)

    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_knowledge_url)

    result = await mcp_client.call_tool(
        tool_name="private_banking",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "system_prompt": PRIVATE_BANKING_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("private_banking_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="private_banking",
            response=f"Private banking encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="private_banking",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "private_banking"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="private_banking",
        response="No response from private banking agent.",
        status="ERROR",
    )
