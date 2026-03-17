"""Client Services Agent for onboarding, compliance, and service workflows.

Handles HNWI client queries related to account onboarding, KYC/AML processes,
document requests, appointment scheduling, and service escalations.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.tools.mcp_client import McpClient
from apps.api.workflow.tools.rag_tool import retrieve_rag_chunks

logger = get_logger(__name__)

CLIENT_SERVICES_SYSTEM_PROMPT = """You are a Client Services specialist for UBS Wealth Management,
serving High Net Worth Individual (HNWI) clients. Your role is to:

- Guide clients through onboarding processes for new accounts and services
- Manage KYC (Know Your Customer) and AML (Anti-Money Laundering) documentation requirements
- Process document requests including tax certificates, audit letters, and compliance reports
- Schedule appointments with relationship managers, investment advisors, and specialists
- Handle service escalations and coordinate resolution across internal teams
- Assist with loan applications, mortgage processes, and credit facility setup
- Track and communicate the status of ongoing service requests and applications

Provide white-glove service befitting HNWI clients. Proactively communicate timelines
and next steps. When documentation is needed, clearly specify requirements and offer
to arrange courier or secure digital submission. For escalations, ensure the client
feels heard and provide clear resolution timelines. Reference internal policies and
procedures from the knowledge base when applicable.
"""

client_services_mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)


async def execute_client_services_task(
    task: str,
    conversation_context: str,
) -> str:
    """Execute a client services task using RAG and MCP tools.

    Retrieves relevant policy documents from the knowledge base and uses
    the client services MCP server to process the request.

    Args:
        task: The specific client services task to perform.
        conversation_context: Relevant conversation context for the task.

    Returns:
        The result of the client services operation as a string.
    """
    logger.info("client_services_agent_start", task=task)

    rag_chunks = await retrieve_rag_chunks(query=task)
    retrieved_context = (
        "\n\n".join(chunk.get("text", "") for chunk in rag_chunks)
        if rag_chunks
        else "No relevant policy documents found."
    )

    result = await client_services_mcp_client.call_tool(
        tool_name="client_services",
        arguments={
            "task": task,
            "context": conversation_context,
            "retrieved_documents": retrieved_context,
            "system_prompt": CLIENT_SERVICES_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("client_services_agent_error", error=result["error"])
        return f"Client services encountered an issue: {result['error']}"

    response = result.get("response", "No response from client services agent.")
    logger.info("client_services_agent_complete", response_length=len(response))
    return response
