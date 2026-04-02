"""FX & Treasury Agent for foreign exchange and multi-currency management.

Handles HNWI client queries related to currency exchange, hedging strategies,
multi-currency account management, and treasury products.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

FX_TREASURY_SYSTEM_PROMPT = """# ROLE
You are a Foreign Exchange (FX) & Treasury Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
1. Market Insights: FX trends, rate forecasts, and risk analysis.
2. Currency Hedging: Forwards, options, and exposure management.
3. Treasury Optimization: Multi-currency liquidity and cash pooling.

# GUIDELINES
- Provide structured, factual insights in JSON.
- Identify potential currency exposure and optimal allocation.
- Do NOT provide unsolicited advice or personal investment opinions.
"""

async def execute_fx_treasury_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a foreign exchange or treasury task using the MCP-connected tools.

    Args:
        task: The specific FX or treasury task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the FX/treasury operation as a SpecialistAgentOutput.
    """
    logger.info("fx_treasury_agent_start", task=task)

    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)

    result = await mcp_client.call_tool(
        tool_name="fx_treasury",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "system_prompt": FX_TREASURY_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("fx_treasury_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="fx_treasury",
            response=f"FX & treasury encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="fx_treasury",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "fx_treasury"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="fx_treasury",
        response="No response from FX & treasury agent.",
        status="ERROR",
    )
