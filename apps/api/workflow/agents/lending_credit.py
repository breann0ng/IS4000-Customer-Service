"""Lending & Credit Agent for loan facilities and structured financing.

Handles HNWI client queries related to Lombard lending, mortgage financing,
credit lines, structured lending solutions, and margin facilities.
"""

from apps.api.config import settings
from apps.api.customers.registry import DEFAULT_CUSTOMER_ID
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient

logger = get_logger(__name__)

LENDING_CREDIT_SYSTEM_PROMPT = """# ROLE AND SYSTEM BOUNDARIES
You are a Lending & Credit Specialist for UBS Wealth Management, serving High Net Worth
Individual (HNWI) clients.
You operate as a **low-autonomy analytical agent** within a multi-agent system.

Your role is to **interpret client data, portfolio details, and credit facility information**
to produce structured, factual insights in **JSON format only**.

You do NOT:
- Execute transactions or approve facilities
- Provide unsolicited advice or personal opinions
- Format responses for end-user readability (handled by the downstream synthesiser agent)
- Replace legal, compliance, or credit committee review
- Estimate, fabricate, or generate your own financial figures — you MUST use the EXACT
  numerical values from the provided client data for AUM, portfolio values, facility limits,
  drawn amounts, and all other financial figures

---

# CORE RESPONSIBILITIES

1. Evaluate lending capacity:
   - Lombard lending against investment portfolios
   - Mortgage eligibility for residential/commercial properties
   - Revolving credit lines, overdrafts, and margin facilities

2. Analytical credit structuring:
   - Identify possible facility structures based on asset types, liquidity, and risk concentration
   - Highlight internal constraints (concentration limits, collateral haircuts, eligibility rules)

3. Facility monitoring:
   - Detect potential risks such as covenant breaches, margin call triggers, and over-leverage

4. Risk identification:
   - Explicitly flag leverage risks, margin calls, interest rate sensitivity, and liquidity risks

---

# OUTPUT REQUIREMENTS

- **Always return a JSON object** in the following schema:

```json
{
  "facility_type": "",
  "client_portfolio_summary": {
    "total_value": 0.0,
    "liquid_assets": 0.0,
    "illiquid_assets": 0.0
  },
  "borrowing_capacity_estimate": 0.0,
  "ltv_range": {
    "minimum": 0.0,
    "maximum": 0.0
  },
  "collateral_requirements": [
    {
      "asset_type": "",
      "haircut_percentage": 0.0
    }
  ],
  "key_constraints": [],
  "risk_flags": [],
  "requires_escalation": false,
  "notes": ""
}
"""

lending_credit_mcp_client = McpClient(server_url=settings.mcp_banking_ops_url)


async def execute_lending_credit_task(
    task: str,
    conversation_context: str,
    customer_id: str = DEFAULT_CUSTOMER_ID,
) -> str:
    """Execute a lending and credit task using the MCP-connected tools.

    Args:
        task: The specific lending or credit task to perform.
        conversation_context: Relevant conversation context for the task.
        customer_id: The unique identifier of the customer.

    Returns:
        The result of the lending operation as a string.
    """
    logger.info("lending_credit_agent_start", task=task)

    result = await lending_credit_mcp_client.call_tool(
        tool_name="lending_credit",
        arguments={
            "task": task,
            "context": conversation_context,
            "customer_id": customer_id,
            "system_prompt": LENDING_CREDIT_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("lending_credit_agent_error", error=result["error"])
        return f"Lending & credit encountered an issue: {result['error']}"

    response = result.get("response", "No response from lending & credit agent.")
    logger.info("lending_credit_agent_complete", response_length=len(response))
    return response
