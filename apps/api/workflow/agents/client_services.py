"""Client Services Agent for onboarding, compliance, and service workflows.

Handles HNWI client queries related to account onboarding, KYC/AML processes,
document requests, appointment scheduling, and service escalations.
"""

from apps.api.config import settings
from apps.api.logging_config import get_logger
from apps.api.workflow.state import SpecialistAgentOutput
from apps.api.workflow.tools.mcp_client import McpClient
from apps.api.workflow.tools.rag_tool import retrieve_rag_chunks

logger = get_logger(__name__)

CLIENT_SERVICES_SYSTEM_PROMPT = """# ROLE
You are a Client Services Specialist for UBS Wealth Management, serving High Net Worth Individual (HNWI) clients. 

# CORE RESPONSIBILITIES
1. Onboarding & Documentation: KYC/AML, account opening, audit document requests.
2. Appointment & Escalation Management: Scheduling with RMs, tracking service issues.
3. Loan & Credit Support: Application status and documentation requirements.

# GUIDELINES
- Provide structured status updates in JSON.
- Focus on operational facts and next steps.
- Do NOT provide investment advice.
"""

async def execute_client_services_task(
    task: str,
    conversation_context: str,
    username: str,
) -> SpecialistAgentOutput:
    """Execute a client services task using RAG and MCP tools.

    Retrieves relevant policy documents from the knowledge base and uses
    the client services MCP server to process the request.

    Args:
        task: The specific client services task to perform.
        conversation_context: Relevant conversation context for the task.
        username: The username of the authenticated persona.

    Returns:
        The result of the client services operation as a SpecialistAgentOutput.
    """
    logger.info("client_services_agent_start", task=task)

    # Initialize client inside handler to pick up latest environment settings
    mcp_client = McpClient(server_url=settings.mcp_service_workflow_url)

    rag_chunks = await retrieve_rag_chunks(query=task)
    retrieved_context = (
        "\n\n".join(chunk.get("text", "") for chunk in rag_chunks)
        if rag_chunks
        else "No relevant policy documents found."
    )

    result = await mcp_client.call_tool(
        tool_name="client_services",
        arguments={
            "task": task,
            "context": conversation_context,
            "username": username,
            "retrieved_documents": retrieved_context,
            "system_prompt": CLIENT_SERVICES_SYSTEM_PROMPT,
        },
    )

    if "error" in result:
        logger.error("client_services_agent_error", error=result["error"])
        return SpecialistAgentOutput(
            agent_name="client_services",
            response=f"Client services encountered an issue: {result['error']}",
            status="ERROR",
            next_steps=["Please try again or contact your RM."],
        )

    # Handle both new structured dict and legacy string responses
    if isinstance(result, str):
        return SpecialistAgentOutput(
            agent_name="client_services",
            response=result,
            status="COMPLETED",
        )

    if isinstance(result, dict) and "response" in result:
        # Ensure agent_name is present
        if "agent_name" not in result:
            result["agent_name"] = "client_services"
        return SpecialistAgentOutput(**result)

    return SpecialistAgentOutput(
        agent_name="client_services",
        response="No response from client services agent.",
        status="ERROR",
    )
