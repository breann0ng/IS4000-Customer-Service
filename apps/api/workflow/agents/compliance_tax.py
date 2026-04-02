"""Compliance & Tax Agent for regulatory and tax reporting inquiries.

Handles HNWI client queries related to cross-border tax obligations,
regulatory compliance, CRS/FATCA reporting, and documentation requirements.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient
from apps.api.workflow.tools.rag_tool import retrieve_rag_chunks

logger = get_logger(__name__)

COMPLIANCE_TAX_SYSTEM_PROMPT = """# ROLE
You are a Compliance & Tax Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
1. Tax Reporting & Documentation: CRS, FATCA, jurisdiction-specific reporting.
2. Regulatory Compliance Guidance: AML, source-of-wealth, regulatory updates.
3. Portfolio & Investment Compliance: Tax-efficient structuring guidance.

# GUIDELINES
- Provide structured, factual insights in JSON.
- Flag areas of potential non-compliance or missing documentation.
- Do NOT provide binding personal tax advice.
"""

async def execute_compliance_tax_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a compliance or tax task using RAG and MCP tools.

    Retrieves relevant regulatory documents from the knowledge base and uses
    the compliance MCP server to process the request.

    Args:
        task: The specific compliance or tax task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the compliance operation as a SpecialistAgentOutput.
    """
    logger.info("compliance_tax_agent_start", task=task)

    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_knowledge_url)

    rag_chunks = await retrieve_rag_chunks(query=task)
    retrieved_context = (
        "\n\n".join(chunk.get("text", "") for chunk in rag_chunks)
        if rag_chunks
        else "No relevant regulatory documents found."
    )

    result = await mcp_client.call_tool(
        tool_name="compliance_tax",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "retrieved_documents": retrieved_context,
            "system_prompt": COMPLIANCE_TAX_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("compliance_tax_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="compliance_tax",
            response=f"Compliance & tax encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="compliance_tax",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "compliance_tax"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="compliance_tax",
        response="No response from compliance & tax agent.",
        status="ERROR",
    )
