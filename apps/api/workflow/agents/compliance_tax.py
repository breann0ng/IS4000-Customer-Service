"""Compliance & Tax Agent for regulatory and tax reporting inquiries.

Handles HNWI client queries related to cross-border tax obligations,
regulatory compliance, CRS/FATCA reporting, and documentation requirements.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient
from apps.api.workflow.tools.rag_tool import retrieve_rag_chunks

logger = get_logger(__name__)

COMPLIANCE_TAX_SYSTEM_PROMPT = """You are a Compliance & Tax specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Explain tax reporting obligations including CRS, FATCA, and jurisdiction-specific requirements
- Assist with cross-border tax documentation and withholding tax reclaim processes
- Provide guidance on regulatory changes affecting client accounts and investments
- Support KYC refresh processes and beneficial ownership documentation
- Clarify anti-money laundering (AML) requirements and source-of-wealth documentation
- Guide clients on tax-efficient investment structuring within regulatory boundaries
- Assist with estate and inheritance tax considerations across multiple jurisdictions
- Provide regulatory compliance updates relevant to the client's portfolio

Always provide accurate regulatory information and clearly distinguish between
general guidance and specific tax advice. Recommend that clients consult their
personal tax advisors for binding opinions. Reference relevant regulatory frameworks
and policy documents from the knowledge base when applicable. Never suggest
non-compliant structures or tax avoidance schemes.
"""

compliance_tax_mcp_client = McpClient(server_url=settings.mcp_knowledge_url)


async def execute_compliance_tax_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a compliance or tax task using RAG and MCP tools.

    Retrieves relevant regulatory documents from the knowledge base and uses
    the compliance MCP server to process the request.

    Args:
        task: The specific compliance or tax task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the compliance operation as a string.
    """
    logger.info("compliance_tax_agent_start", task=task)

    rag_chunks = await retrieve_rag_chunks(query=task)
    retrieved_context = (
        "\n\n".join(chunk.get("text", "") for chunk in rag_chunks)
        if rag_chunks
        else "No relevant regulatory documents found."
    )

    result = await compliance_tax_mcp_client.call_tool(
        tool_name="compliance_tax",
        arguments={
            "task": task,
            "context": conversation_context,
            "retrieved_documents": retrieved_context,
            "system_prompt": COMPLIANCE_TAX_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("compliance_tax_agent_error", error=result["error"])
        return f"Compliance & tax encountered an issue: {result['error']}"

    response = result.get("response", "No response from compliance & tax agent.")
    logger.info("compliance_tax_agent_complete", response_length=len(response))
    return response
