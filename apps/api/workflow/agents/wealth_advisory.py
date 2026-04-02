"""Wealth Advisory Agent for portfolio management and investment guidance.

Handles HNWI client queries related to portfolio performance, asset allocation,
market insights, structured products, and investment strategy.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

WEALTH_ADVISORY_SYSTEM_PROMPT = """# ROLE
You are a Wealth Advisory Specialist representing UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
- Portfolio analysis using actual client allocation and performance data.
- Personalized investment guidance aligned with the client’s risk profile.
- Market insights linked to current client positioning.
- High-level product education (structured products, alternatives).

# GUIDELINES
- Provide structured, personalized wealth insights in JSON.
- Always extract and use relevant fields from the provided client profile.
- Do NOT provide tax, legal, or compliance advice.
"""

async def execute_wealth_advisory_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a wealth advisory task using the MCP-connected tools.

    Args:
        task: The specific wealth advisory task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the wealth advisory operation as a SpecialistAgentOutput.
    """
    logger.info("wealth_advisory_agent_start", task=task)
    
    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_banking_ops_url)

    result = await mcp_client.call_tool(
        tool_name="wealth_advisory",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "system_prompt": WEALTH_ADVISORY_SYSTEM_PROMPT,
        },
    )


    if "error" in result:
        logger.error("wealth_advisory_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="wealth_advisory",
            response=f"Wealth advisory encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="wealth_advisory",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "wealth_advisory"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="wealth_advisory",
        response="No response from wealth advisory agent.",
        status="ERROR",
    )

