"""Lending & Credit Agent for loan facilities and structured financing.

Handles HNWI client queries related to Lombard lending, mortgage financing,
credit lines, structured lending solutions, and margin facilities.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

LENDING_CREDIT_SYSTEM_PROMPT = """# ROLE
You are a Lending & Credit Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
1. Evaluate lending capacity: Lombard lending, mortgages, credit lines.
2. Credit structuring: LTV estimates, collateral haircuts, eligibility.
3. Facility monitoring: Risk identification, margin calls, and over-leverage.

# GUIDELINES
- Provide structured, factual insights in JSON.
- Flag leverage risks, margin calls, and interest rate sensitivity.
- Do NOT provide unsolicited advice or personal opinions.
"""

async def execute_lending_credit_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a lending and credit task using the MCP-connected tools.

    Args:
        task: The specific lending or credit task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the lending operation as a SpecialistAgentOutput.
    """
    logger.info("lending_credit_agent_start", task=task)

    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_banking_ops_url)

    result = await mcp_client.call_tool(
        tool_name="lending_credit",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "system_prompt": LENDING_CREDIT_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("lending_credit_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="lending_credit",
            response=f"Lending & credit encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="lending_credit",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "lending_credit"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="lending_credit",
        response="No response from lending & credit agent.",
        status="ERROR",
    )
