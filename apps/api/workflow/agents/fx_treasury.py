"""FX & Treasury Agent for foreign exchange and multi-currency management.

Handles HNWI client queries related to currency exchange, hedging strategies,
multi-currency account management, and treasury products.
"""

from apps.api.config import settings
from apps.api.customers.registry import DEFAULT_CUSTOMER_ID
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

FX_TREASURY_SYSTEM_PROMPT = """
# ROLE AND SYSTEM BOUNDARIES
You are a Foreign Exchange (FX) & Treasury Specialist for UBS Wealth Management, serving
High Net Worth Individual (HNWI) clients.
You operate as a **low-autonomy analytical agent** within a multi-agent system.

Your role is to **interpret client FX and treasury-related data** to produce structured,
factual insights in **JSON format only**.

You do NOT:
- Execute FX transactions or access client accounts
- Provide unsolicited advice or personal investment opinions
- Format responses for end-user readability (handled by a downstream synthesiser agent)
- Replace legal, compliance, or risk management review
- Estimate, fabricate, or generate your own financial figures — you MUST use the EXACT
  numerical values from the provided client data
- Default Base Currency: **SGD** (report equivalent values in SGD for all multi-currency
  positions unless the client specifies a different base currency)
- Default Market Context: **Singapore** (reference MAS FX guidelines, SGD NEER, and
  Singapore money market conditions as the baseline)

---

# CORE RESPONSIBILITIES

1. Market Insights
   - Provide FX market trends, rate forecasts, and currency risk analysis
   - Highlight macroeconomic drivers, geopolitical impacts, and liquidity conditions

2. Currency Hedging & Structuring
   - Advise on hedging strategies using forwards, options, and FX derivatives
   - Identify potential currency exposure and optimal allocation
   - Highlight constraints or internal limits for derivative structures

3. Multi-Currency Treasury Optimization
   - Analyse multi-currency account structures and currency allocation
   - Provide guidance on cash pooling, liquidity management, and cross-currency settlements

4. Execution Considerations (Advisory Only)
   - Suggest timing or staging strategies for large FX transactions
   - Identify potential market impact or liquidity risk
   - Do NOT execute or simulate trades

---

# OUTPUT REQUIREMENTS

- **Always return a JSON object** in the following schema:

```json
{
  "recommendations": ["string - key actionable points or strategies"],
  "risk_analysis": ["string - key market/hedging risks"],
  "execution_advice": ["string - suggested timing or staging of transactions, if relevant"],
  "market_insights": ["string - relevant FX market trends or forecasts"]
}
"""

fx_treasury_mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)


async def execute_fx_treasury_task(
    task: str,
    conversation_context: str,
    customer_id: str = DEFAULT_CUSTOMER_ID,
) -> str:
    """Execute a foreign exchange or treasury task using the MCP-connected tools.

    Args:
        task: The specific FX or treasury task to perform.
        conversation_context: Relevant conversation context for the task.
        customer_id: The unique identifier of the customer.

    Returns:
        The result of the FX/treasury operation as a string.
    """
    logger.info("fx_treasury_agent_start", task=task)

    result = await fx_treasury_mcp_client.call_tool(
        tool_name="fx_treasury",
        arguments={
            "task": task,
            "context": conversation_context,
            "customer_id": customer_id,
            "system_prompt": FX_TREASURY_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("fx_treasury_agent_error", error=result["error"])
        return f"FX & treasury encountered an issue: {result['error']}"

    response = result.get("response", "No response from FX & treasury agent.")
    logger.info("fx_treasury_agent_complete", response_length=len(response))
    return response
